"""Resolve authentication + tenant context for HTTP routes."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from koraku.core.auth import AuthResult, auth_error_detail, verify_request_auth
from koraku.core.config import settings
from koraku.core.tenant import ORG_ID_HEADER, TenantContext


@dataclass(frozen=True)
class ResolvedRequestAuth:
    auth: AuthResult
    tenant: TenantContext

    @property
    def sub(self) -> str | None:
        return self.auth.sub

    @property
    def org_id(self) -> str | None:
        return self.tenant.org_id

    @property
    def auth_ok(self) -> bool:
        return self.auth.ok

    def require_chat_access(self) -> None:
        if not settings.require_auth_for_chat:
            return
        if (settings.auth_backend or "").strip().lower() == "none":
            return
        if not self.auth_ok or self.auth.reason == "ok_anonymous":
            raise HTTPException(
                status_code=401,
                detail=auth_error_detail(self.auth.reason),
            )


def _org_id_from_request(request: Request) -> str | None:
    raw = request.headers.get(ORG_ID_HEADER) or request.headers.get(ORG_ID_HEADER.upper())
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip()


def resolve_request_auth(request: Request) -> ResolvedRequestAuth:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    auth = verify_request_auth(auth_header)
    org_id = _org_id_from_request(request) if auth.sub else None
    return ResolvedRequestAuth(auth=auth, tenant=TenantContext(org_id=org_id, user_id=auth.sub))
