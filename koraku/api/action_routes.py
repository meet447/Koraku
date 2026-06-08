"""HTTP routes for one-click actions and event automations."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from koraku.actions.pending_actions import execute_action
from koraku.automations.event_triggers import trigger_event
from koraku.core.request_auth import resolve_request_auth

router = APIRouter(tags=["actions"])


class ActionExecuteBody(BaseModel):
    action_id: str = Field(..., max_length=64)
    overrides: dict[str, Any] | None = None


class EventTriggerBody(BaseModel):
    payload: dict[str, Any] | None = None


@router.post("/api/action/execute")
async def action_execute(body: ActionExecuteBody, request: Request) -> dict[str, Any]:
    auth = resolve_request_auth(request)
    auth.require_chat_access()
    result = await execute_action(body.action_id.strip(), overrides=body.overrides)
    if not result.get("ok"):
        code = str(result.get("error") or "failed")
        status = 404 if code == "not_found" else 400
        raise HTTPException(status_code=status, detail=code)
    return result


@router.post("/api/automations/trigger/{event_key}")
async def automation_event_trigger(
    event_key: str,
    body: EventTriggerBody,
    request: Request,
) -> dict[str, Any]:
    auth = resolve_request_auth(request)
    auth.require_chat_access()
    secret = request.headers.get("x-koraku-event-secret") or request.headers.get("X-Koraku-Event-Secret")
    agent = getattr(request.app.state, "koraku_agent", None)
    result = await trigger_event(
        event_key,
        payload=body.payload,
        agent=agent,
        secret=secret,
    )
    if not result.get("ok"):
        err = str(result.get("error") or "failed")
        status = 404 if err == "no_matching_automation" else 403 if err == "invalid_secret" else 400
        raise HTTPException(status_code=status, detail=err)
    return result
