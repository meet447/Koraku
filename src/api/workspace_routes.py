"""Cloud workspace file tree + read (Blaxel session folder)."""
from __future__ import annotations

import posixpath
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.core.config import settings
from src.integrations.blaxel_runtime import (
    cloud_blaxel_block_reason,
    ensure_chat_sandbox,
    session_workspace_root_posix,
)
from src.integrations.cloud_user import effective_cloud_user_id

router = APIRouter(prefix="/api/workspace", tags=["workspace"])

_MAX_TEXT_FILE_BYTES = 2 * 1024 * 1024
_MAX_BLOB_FILE_BYTES = 12 * 1024 * 1024

_BLOB_MEDIA = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _parse_session_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        uuid.UUID(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="session_id must be a UUID") from e
    return s


def safe_join_under_session_root(root: str, rel: str) -> str:
    """Resolve ``rel`` under ``root``; raises ``HTTPException`` if path escapes."""
    root = root.rstrip("/") or "/"
    rel = (rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        return root
    candidate = posixpath.normpath(posixpath.join(root, rel))
    prefix = root if root.endswith("/") else root + "/"
    if candidate == root or candidate.startswith(prefix):
        return candidate
    raise HTTPException(status_code=400, detail="path must stay under the session workspace")


def _require_cloud_workspace() -> None:
    reason = cloud_blaxel_block_reason(settings)
    if reason:
        raise HTTPException(status_code=503, detail=reason)


@router.get("/tree")
async def workspace_tree(
    session_id: str = Query(..., min_length=8),
    path: str = Query("", max_length=2048),
) -> dict[str, Any]:
    """List files and subdirectories under the chat session folder (or a subpath)."""
    _require_cloud_workspace()
    sid = _parse_session_id(session_id)
    uid = effective_cloud_user_id()
    root = session_workspace_root_posix(uid, sid, settings)
    target = safe_join_under_session_root(root, path)
    try:
        sb = await ensure_chat_sandbox(sid, settings, user_id=uid)
        directory = await sb.fs.ls(target)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Blaxel: {e}") from e

    files = [
        {"name": f.name, "path": f.path, "size": getattr(f, "size", 0)}
        for f in (directory.files or [])
    ]
    dirs = [{"name": d.name, "path": d.path} for d in (directory.subdirectories or [])]
    return {"root": root, "path": target, "files": files, "directories": dirs}


@router.get("/file")
async def workspace_read_file(
    session_id: str = Query(..., min_length=8),
    path: str = Query(..., min_length=1, max_length=2048),
) -> dict[str, Any]:
    """Read a text file under the session workspace (size-capped)."""
    _require_cloud_workspace()
    sid = _parse_session_id(session_id)
    uid = effective_cloud_user_id()
    root = session_workspace_root_posix(uid, sid, settings)
    target = safe_join_under_session_root(root, path)
    try:
        sb = await ensure_chat_sandbox(sid, settings, user_id=uid)
        text = await sb.fs.read(target)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Blaxel: {e}") from e

    raw = text if isinstance(text, str) else str(text)
    truncated = len(raw.encode("utf-8")) > _MAX_TEXT_FILE_BYTES
    if truncated:
        raw = raw.encode("utf-8")[:_MAX_TEXT_FILE_BYTES].decode("utf-8", errors="replace")
    return {"path": target, "content": raw, "truncated": truncated}


@router.get("/file/blob")
async def workspace_read_blob(
    session_id: str = Query(..., min_length=8),
    path: str = Query(..., min_length=1, max_length=2048),
) -> Response:
    """Return raw bytes for ``.pdf`` / ``.docx`` (for browser preview)."""
    _require_cloud_workspace()
    sid = _parse_session_id(session_id)
    uid = effective_cloud_user_id()
    root = session_workspace_root_posix(uid, sid, settings)
    target = safe_join_under_session_root(root, path)
    ext = posixpath.splitext(target)[1].lower()
    if ext not in _BLOB_MEDIA:
        raise HTTPException(
            status_code=400,
            detail=f"binary preview only supports: {', '.join(sorted(_BLOB_MEDIA))}",
        )
    try:
        sb = await ensure_chat_sandbox(sid, settings, user_id=uid)
        data = await sb.fs.read_binary(target)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Blaxel: {e}") from e
    if not isinstance(data, (bytes, bytearray)):
        raise HTTPException(status_code=502, detail="unexpected binary payload")
    body = bytes(data)
    if len(body) > _MAX_BLOB_FILE_BYTES:
        raise HTTPException(status_code=413, detail="file too large for preview")
    return Response(content=body, media_type=_BLOB_MEDIA[ext])
