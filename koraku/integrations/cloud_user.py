"""Resolved cloud user id for Blaxel workspace layout (Supabase ``sub`` when authenticated)."""
from __future__ import annotations

import contextvars
import os
from contextvars import Token

HARDCODED_CLOUD_USER_ID = "dev-user-1"

_cloud_uid: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "koraku_cloud_uid",
    default=None,
)


def set_cloud_user_id(user_id: str | None) -> Token | None:
    """Bind Blaxel workspace paths to a signed-in user for the current async context."""
    if not user_id or not str(user_id).strip():
        return None
    return _cloud_uid.set(str(user_id).strip())


def reset_cloud_user_id(token: Token | None) -> None:
    if token is not None:
        _cloud_uid.reset(token)


def effective_cloud_user_id() -> str:
    """
    Prefer per-request user id (JWT ``sub``); else ``KORAKU_CLOUD_USER_ID``; else dev default.

    ``KORAKU_CLOUD_USER_ID`` is for local scripts or tests without a browser session.
    """
    ctx = _cloud_uid.get()
    if ctx and ctx.strip():
        return ctx.strip()
    env = (os.environ.get("KORAKU_CLOUD_USER_ID", "") or "").strip()
    if env:
        return env
    return HARDCODED_CLOUD_USER_ID
