"""Resolved authenticated user for sandbox workspace layout (tenant-scoped when org is set)."""
from __future__ import annotations

import contextvars
from contextvars import Token

from koraku.core.tenant import TenantContext, effective_tenant_org_id

_runtime_uid: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "koraku_runtime_uid",
    default=None,
)


def set_runtime_user_id(user_id: str | None) -> Token | None:
    """Bind Blaxel workspace paths to a signed-in user for the current async context."""
    if not user_id or not str(user_id).strip():
        return None
    return _runtime_uid.set(str(user_id).strip())


def reset_runtime_user_id(token: Token | None) -> None:
    if token is not None:
        _runtime_uid.reset(token)


def effective_auth_user_sub() -> str:
    """Auth subject for the current request (JWT sub or API-key subject)."""
    ctx = _runtime_uid.get()
    if not ctx or not str(ctx).strip():
        raise RuntimeError("Authenticated user required.")
    return str(ctx).strip()


def effective_runtime_user_id() -> str:
    """Per-request storage scope (``org_id/user_id``) for sandbox paths."""
    org = effective_tenant_org_id()
    uid = effective_auth_user_sub()
    if org:
        return TenantContext(org_id=org, user_id=uid).storage_scope_id()
    return uid
