"""Personalization: Supabase per-user profile when configured, else ``.koraku/`` on server cwd."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.core.auth_supabase import SUPABASE_JWT_REQUEST_ERROR_MESSAGES, verify_supabase_jwt_bearer_detail
from src.integrations.supabase_personalization import (
    fetch_personalization_sync,
    supabase_personalization_configured,
    upsert_personalization_sync,
)
from src.workspace.context import read_personalization_files, write_personalization_files
from src.workspace.paths import workspace_dir

router = APIRouter(prefix="/api", tags=["personalization"])


class PersonalizationUpdate(BaseModel):
    """Agent display name plus long-form memory and soul text."""

    agent_name: str = Field(default="", max_length=120)
    memory: str = Field(default="", max_length=600_000)
    soul: str = Field(default="", max_length=600_000)


def _auth_401(reason: str) -> HTTPException:
    msg = SUPABASE_JWT_REQUEST_ERROR_MESSAGES.get(reason, reason)
    return HTTPException(status_code=401, detail=msg)


@router.get("/personalization")
async def personalization_get(request: Request):
    """Load profile from Supabase (signed-in) or from ``.koraku/`` when Supabase is not configured."""
    if supabase_personalization_configured():
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        jwt = verify_supabase_jwt_bearer_detail(auth_header)
        if not jwt.ok:
            raise _auth_401(jwt.reason)
        row = await asyncio.to_thread(fetch_personalization_sync, jwt.sub or "")
        if row is None:
            raise HTTPException(status_code=502, detail="Could not load personalization from database.")
        return row
    ws = workspace_dir()
    return read_personalization_files(ws)


@router.put("/personalization")
async def personalization_put(request: Request, body: PersonalizationUpdate):
    """Persist profile to Supabase (signed-in) or to ``.koraku/`` when Supabase is not configured."""
    if supabase_personalization_configured():
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        jwt = verify_supabase_jwt_bearer_detail(auth_header)
        if not jwt.ok:
            raise _auth_401(jwt.reason)
        if not jwt.sub:
            raise _auth_401("invalid_token")
        try:
            await asyncio.to_thread(
                upsert_personalization_sync,
                jwt.sub,
                body.agent_name,
                body.memory,
                body.soul,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not save personalization: {e}") from e
        return {"ok": True}
    ws = workspace_dir()
    write_personalization_files(ws, body.agent_name, body.memory, body.soul)
    return {"ok": True}
