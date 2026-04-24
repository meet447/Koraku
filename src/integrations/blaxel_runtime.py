"""Blaxel sandboxes for ``execution_target=cloud`` (isolated file + shell tools)."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from src.core.config import Settings

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_BLAXEL_AUTH_HELP = (
    "Blaxel rejected these credentials. Create a long-lived API key at "
    "https://app.blaxel.ai/profile/security and set BL_API_KEY in the server .env (single line, "
    "no quotes or trailing spaces). Set BL_WORKSPACE to the workspace slug from your browser URL "
    "https://app.blaxel.ai/<slug> — the key must belong to that workspace. Restart the API after "
    "changing .env."
)


def _blaxel_error_looks_like_auth_failure(exc: BaseException) -> bool:
    """HTTP 401/403 or common auth phrases from Blaxel / httpx."""
    parts: list[str] = [f"{type(exc).__name__} {exc}".lower()]
    resp = getattr(exc, "response", None)
    if resp is not None:
        sc = getattr(resp, "status_code", None)
        if sc in (401, 403):
            return True
        try:
            txt = getattr(resp, "text", "") or ""
            if isinstance(txt, str):
                parts.append(txt.lower())
        except Exception:
            pass
    cause = exc.__cause__
    if isinstance(cause, BaseException):
        parts.append(f"{type(cause).__name__} {cause}".lower())
    combined = " ".join(parts)
    return any(
        m in combined
        for m in (
            "authorization",
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "invalid token",
            "authentication",
            "access denied",
        )
    )


try:
    from blaxel.core import SandboxInstance as _SandboxInstance  # type: ignore import-not-found

    _BLAXEL_IMPORT_ERROR: Exception | None = None
except Exception as e:  # pragma: no cover - optional dependency
    _SandboxInstance = None
    _BLAXEL_IMPORT_ERROR = e


def blaxel_sdk_available() -> bool:
    return _SandboxInstance is not None


def blaxel_import_error_message() -> str | None:
    if _BLAXEL_IMPORT_ERROR is None:
        return None
    return str(_BLAXEL_IMPORT_ERROR)


def blaxel_credentials_configured(settings: Settings) -> bool:
    return bool((settings.bl_workspace or "").strip() and (settings.bl_api_key or "").strip())


def cloud_blaxel_block_reason(settings: Settings) -> str | None:
    """If set, **Cloud** in the UI cannot start — do not fall back to the host repo."""
    if not settings.blaxel_cloud_sandbox_enabled:
        return (
            "Cloud mode uses a Blaxel sandbox only. Set BLAXEL_CLOUD_SANDBOX_ENABLED=true on the "
            "Koraku backend, plus BL_WORKSPACE and BL_API_KEY (see .env.example)."
        )
    if not blaxel_sdk_available():
        ie = blaxel_import_error_message() or "unknown import error"
        return (
            "Cloud mode needs the `blaxel` package in the Python that runs this API. "
            "If you use a venv, start Koraku with that interpreter (e.g. `.venv/bin/python main.py`) "
            "or run `pip install blaxel` for the same `python` your server uses. "
            f"Import error: {ie}"
        )
    if not (settings.bl_api_key or "").strip():
        return "Cloud mode requires BL_API_KEY in the server's environment (.env)."
    if not (settings.bl_workspace or "").strip():
        return (
            "Cloud mode requires BL_WORKSPACE in the server's .env — the workspace slug from "
            "https://app.blaxel.ai/<workspace> in your browser."
        )
    return None


def cloud_chat_uses_blaxel_vm(settings: Settings) -> bool:
    """True when cloud chat can provision a Blaxel VM (no block reason)."""
    return cloud_blaxel_block_reason(settings) is None


def chat_sandbox_name(session_id: str) -> str:
    """Stable DNS-safe name (one sandbox per chat session)."""
    raw = (session_id or "").strip()
    safe = re.sub(r"[^a-zA-Z0-9]+", "", raw)[:40]
    if not safe:
        safe = "session"
    return f"koraku-{safe}"


async def ensure_chat_sandbox(session_id: str, settings: Settings) -> Any:
    """Create or resume the Blaxel VM for this chat session."""
    if _SandboxInstance is None:
        raise RuntimeError(
            "blaxel package is not installed. Add `blaxel` to the environment (see requirements.txt)."
        )
    if not blaxel_credentials_configured(settings):
        raise RuntimeError("Set BL_WORKSPACE and BL_API_KEY for Blaxel sandboxes.")

    name = chat_sandbox_name(session_id)
    spec: dict[str, Any] = {
        "name": name,
        "image": settings.blaxel_sandbox_image,
        "memory": int(settings.blaxel_sandbox_memory_mb),
        "region": settings.blaxel_sandbox_region,
        "labels": {"app": "koraku", "koraku_session": session_id[:36]},
    }
    log.info("Blaxel sandbox ensure name=%s region=%s", name, settings.blaxel_sandbox_region)
    try:
        return await _SandboxInstance.create_if_not_exists(spec)
    except Exception as e:
        if _blaxel_error_looks_like_auth_failure(e):
            raise RuntimeError(_BLAXEL_AUTH_HELP) from e
        raise
