"""Composio integrations API (connections UI)."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from src.core.auth_supabase import verify_supabase_jwt_bearer_detail
from src.integrations import composio as composio_runtime
from src.workspace.paths import workspace_dir

router = APIRouter(prefix="/api/composio", tags=["composio"])


class ComposioConnectBody(BaseModel):
    toolkit: str = Field(..., min_length=2, max_length=64)


async def _composio_request_scope(
    authorization: str | None = Header(None),
) -> AsyncGenerator[None, None]:
    """
    When Composio is configured, require a valid Supabase access token and scope all SDK calls
    to that user's ``sub``. When Composio is off, skip auth so the UI can show browse-only state.
    """
    composio_runtime.configure_workspace_cache(workspace_dir())
    if not composio_runtime.is_configured():
        yield
        return
    jwt_res = verify_supabase_jwt_bearer_detail(authorization)
    if not jwt_res.ok:
        messages = {
            "no_secret": (
                "This token is HS256 but SUPABASE_JWT_SECRET is not set on the backend. "
                "Add it from Supabase → Settings → API (JWT Secret), or use asymmetric (ES256) tokens."
            ),
            "no_header": "Missing Authorization header (Next.js proxy should attach Bearer from Supabase cookies).",
            "bad_scheme": "Authorization must be Bearer <Supabase access_token>.",
            "empty_token": "Bearer token was empty.",
            "unsupported_alg": "JWT signing algorithm is not supported by Koraku.",
            "invalid_issuer": "JWT issuer (iss) is not a trusted Supabase host (*.supabase.co).",
            "expired": "Supabase session expired; sign in again from the web app.",
            "invalid_token": (
                "Invalid Supabase JWT — ensure the web app and backend use the same Supabase project; "
                "for HS256 set SUPABASE_JWT_SECRET; for ES256/RS256 JWKS is fetched from the token iss."
            ),
        }
        status = 503 if jwt_res.reason == "no_secret" else 401
        detail = messages.get(
            jwt_res.reason,
            "Sign in required. Pass Authorization: Bearer <Supabase access_token>.",
        )
        raise HTTPException(status_code=status, detail=f"{detail} (code={jwt_res.reason})")
    uid = jwt_res.sub
    assert uid is not None
    t = composio_runtime.set_composio_request_user(uid)
    try:
        yield
    finally:
        composio_runtime.reset_composio_request_user(t)


@router.get("/overview", dependencies=[Depends(_composio_request_scope)])
async def composio_overview():
    """Connection status + active toolkits for the Connections UI."""
    return {
        "configured": composio_runtime.is_configured(),
        "user_id": composio_runtime.user_id() if composio_runtime.is_configured() else None,
        "connections": composio_runtime.list_connections_summary() if composio_runtime.is_configured() else [],
        "active_toolkits": composio_runtime.active_toolkit_slugs() if composio_runtime.is_configured() else [],
    }


@router.get("/toolkits", dependencies=[Depends(_composio_request_scope)])
async def composio_toolkits_search(q: str = "", limit: int = 48):
    if not composio_runtime.is_configured():
        return {"items": [], "configured": False}
    lim = max(1, min(int(limit), 50))
    return {"items": composio_runtime.search_toolkits(q, limit=lim), "configured": True}


@router.post("/connect", dependencies=[Depends(_composio_request_scope)])
async def composio_connect(body: ComposioConnectBody):
    if not composio_runtime.is_configured():
        raise HTTPException(status_code=503, detail="Set COMPOSIO_API_KEY to connect integrations.")
    try:
        return composio_runtime.start_toolkit_auth(body.toolkit.strip().upper())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
