"""Workspace artifacts for Koraku task rooms and second-brain outputs."""
from __future__ import annotations

import os
import re
from pathlib import PurePosixPath
from typing import Any

_RUN_SAFE = re.compile(r"[^a-z0-9._-]+")
_ARTIFACT_SAFE = re.compile(r"^[A-Za-z0-9._/\-]+$")
_ALLOWED_TYPES = frozenset(
    {
        "plan",
        "sources",
        "notes",
        "evidence",
        "brief",
        "document",
        "spreadsheet",
        "email_draft",
        "workflow",
        "action_log",
        "memory",
    }
)


def normalize_run_slug(raw: str) -> str:
    """Return a stable, filename-safe task room slug."""
    s = (raw or "").strip().lower()
    s = _RUN_SAFE.sub("-", s).strip(".-_")
    return (s or "koraku-task")[:80]


def normalize_artifact_type(raw: str) -> str:
    s = (raw or "").strip().lower()
    return s if s in _ALLOWED_TYPES else "document"


def safe_artifact_relpath(run_slug: str, artifact_path: str) -> str:
    """Path under ``.koraku/runs/<slug>``; rejects traversal and unsafe characters."""
    slug = normalize_run_slug(run_slug)
    raw = (artifact_path or "").strip().replace("\\", "/").lstrip("/")
    if not raw:
        raw = "notes.md"
    if not _ARTIFACT_SAFE.match(raw):
        raise ValueError("artifact_path may only contain letters, numbers, dot, dash, underscore, and slash")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("artifact_path must be a relative path without traversal")
    return str(PurePosixPath(".koraku") / "runs" / slug / path)


def artifact_manifest_entry(
    *,
    run_slug: str,
    artifact_path: str,
    artifact_type: str,
    content_chars: int,
) -> dict[str, Any]:
    relpath = safe_artifact_relpath(run_slug, artifact_path)
    return {
        "run_slug": normalize_run_slug(run_slug),
        "path": relpath,
        "artifact_type": normalize_artifact_type(artifact_type),
        "content_chars": int(content_chars),
    }


def host_artifact_abs_path(workspace: str, run_slug: str, artifact_path: str) -> str:
    """Absolute host path for tests/UI helpers; tool execution should use relative paths."""
    return os.path.join(os.path.abspath(workspace), safe_artifact_relpath(run_slug, artifact_path))
