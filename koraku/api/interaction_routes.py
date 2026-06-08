"""Respond to in-flight AskUser questions and tool approval prompts."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from koraku.agent.pending_interactions import resolve
from koraku.core.request_auth import resolve_request_auth

router = APIRouter(tags=["interaction"])


class InteractionRespondBody(BaseModel):
    interaction_id: str = Field(..., max_length=64)
    answers: dict[str, Any] | None = None
    approved: bool | None = None
    updated_input: dict[str, Any] | None = None


@router.post("/api/interaction/respond")
async def interaction_respond(body: InteractionRespondBody, request: Request) -> dict[str, Any]:
    """Complete a pending AskUser or approval interaction for an active agent run."""
    auth = resolve_request_auth(request)
    auth.require_chat_access()

    payload: dict[str, Any] = {}
    if body.answers is not None:
        payload["answers"] = body.answers
    if body.approved is not None:
        payload["approved"] = body.approved
    if body.updated_input is not None:
        payload["updated_input"] = body.updated_input
    if not payload:
        raise HTTPException(status_code=400, detail="Provide answers and/or approved")

    ok = await resolve(body.interaction_id.strip(), payload)
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown or expired interaction_id")
    return {"ok": True}
