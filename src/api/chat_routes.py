"""Chat UI API: model list + SSE ``/stream``."""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from src.agent import _step_budget, get_or_create_chat_session
from src.agent.unconfigured import run_unconfigured
from src.agent.run import AgentRunContext
from src.core.config import settings
from src.llm.catalog import (
    configured_provider_ids,
    resolve_effective_model,
    ui_chat_models_async,
)
from src.streaming.orchids_sse import KorakuStreamState, map_koraku_stream_events
from src.tools import AVAILABLE_TOOLS
from src.workspace.paths import workspace_dir

if TYPE_CHECKING:
    from src.agent import Agent

router = APIRouter(tags=["chat"])


class StreamImagePart(BaseModel):
    """One inline image as raw base64 (no ``data:`` URL prefix)."""

    media_type: str = Field(..., max_length=64)
    data: str = Field(..., max_length=14_000_000)

    @field_validator("media_type")
    @classmethod
    def must_be_image_mime(cls, v: str) -> str:
        m = v.strip().lower()
        allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
        if m not in allowed:
            raise ValueError("media_type must be image/jpeg, image/png, image/gif, or image/webp")
        return m


class StreamChatBody(BaseModel):
    """JSON body for ``POST /stream`` (SSE response)."""

    msg: str = Field(default="", max_length=400_000)
    model: str = ""
    provider: str = ""
    session_id: str = ""
    client_tz: str | None = None
    client_locale: str | None = None
    images: list[StreamImagePart] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def msg_or_images(self) -> "StreamChatBody":
        if not (self.msg.strip() or self.images):
            raise ValueError("Provide a non-empty message and/or at least one image")
        return self


def format_sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _normalize_client_hint(value: str | None) -> str | None:
    s = (value or "").strip()
    return s or None


def _resolve_stream_provider_model(model: str, provider: str) -> tuple[str, str]:
    active = (settings.llm_provider or "custom_openai").strip().lower()
    eff_provider = (provider or "").strip().lower() or active
    if eff_provider not in ("anthropic", "fireworks", "custom_openai", "bonsai"):
        eff_provider = active
    from src.llm.catalog import is_provider_configured

    if not is_provider_configured(eff_provider):
        ids = configured_provider_ids()
        eff_provider = ids[0] if ids else active
    resolved_model = resolve_effective_model(model, provider_id=eff_provider)
    return eff_provider, resolved_model


async def _stream_agent_sse(
    msg: str,
    *,
    images: list[StreamImagePart],
    model: str,
    provider: str,
    session_id: str | None,
    client_tz: str | None,
    client_locale: str | None,
    agent: "Agent | None",
    server_mode: str,
) -> AsyncIterator[str]:
    session = get_or_create_chat_session(session_id)
    eff_provider, resolved_model = _resolve_stream_provider_model(model, provider)

    stream_state = KorakuStreamState()
    stream_state.resolved_model = resolved_model if server_mode == "live" else "koraku-unconfigured"
    stream_state.eff_provider = eff_provider if server_mode == "live" else "unconfigured"

    yield format_sse(
        stream_state.started_payload(stream_state.resolved_model, chat_session_id=session.session_id)
    )
    await asyncio.sleep(0)
    yield format_sse(stream_state.s2_stream_payload())
    await asyncio.sleep(0)
    yield format_sse(stream_state.route_decision_payload())
    await asyncio.sleep(0)

    budget = msg.strip() or ("[images]" if images else "")
    mode_hint, max_steps_hint = _step_budget(budget)
    tz = _normalize_client_hint(client_tz)
    loc = _normalize_client_hint(client_locale)
    koraku_boot = {
        "workspace_session_id": session.session_id,
        "server_mode": server_mode,
        "mode": mode_hint,
        "max_steps": max_steps_hint,
        "tool_names": [t.name for t in AVAILABLE_TOOLS],
        "provider": stream_state.eff_provider,
        "model": stream_state.resolved_model,
        "client_timezone": tz,
        "client_locale": loc,
    }
    yield format_sse(stream_state.system_init_payload(workspace_dir(), koraku_boot))
    await asyncio.sleep(0)

    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    def emit(event: dict) -> None:
        queue.put_nowait(event)

    async def run_agent() -> None:
        try:
            img_payload = [{"media_type": p.media_type, "data": p.data} for p in images]
            agent_iter = (
                run_unconfigured(msg, session, emit, image_parts=img_payload)
                if agent is None
                else agent.run(
                    msg,
                    session,
                    emit,
                    context=AgentRunContext(
                        model=model,
                        provider=provider,
                        client_timezone=tz,
                        client_locale=loc,
                        image_parts=img_payload,
                    ),
                )
            )
            async for _ in agent_iter:
                pass
        except Exception as e:
            emit({"type": "agent.error", "data": {"error": str(e)}})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(run_agent())

    idle = max(5.0, float(settings.sse_keepalive_seconds))
    ping = f"event: ping\ndata: {json.dumps({})}\n\n"
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=idle)
        except asyncio.TimeoutError:
            if task.done():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    break
            else:
                yield ping
                continue
        if event is None:
            break
        for row in map_koraku_stream_events(event, stream_state):
            yield format_sse(row)
            await asyncio.sleep(0)

    await task

    yield "event: done\n\n"


@router.get("/api/chat-models")
async def chat_models():
    """Model IDs for the chat UI dropdown (per provider + optional CHAT_MODEL_OPTIONS)."""
    return await ui_chat_models_async()


@router.post("/stream")
async def stream_endpoint_post(body: StreamChatBody, request: Request):
    """SSE streaming agent chat. Use JSON body (large prompts); response is ``text/event-stream``."""
    agent = getattr(request.app.state, "koraku_agent", None)
    server_mode = getattr(request.app.state, "server_mode", "unconfigured")

    async def event_generator() -> AsyncIterator[str]:
        async for chunk in _stream_agent_sse(
            body.msg.strip(),
            images=body.images,
            model=body.model,
            provider=body.provider,
            session_id=(body.session_id.strip() or None),
            client_tz=body.client_tz,
            client_locale=body.client_locale,
            agent=agent,
            server_mode=server_mode,
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stream")
async def stream_endpoint_get_deprecated():
    """``GET /stream`` was removed; chat uses ``POST /stream`` with a JSON body."""
    raise HTTPException(
        status_code=405,
        headers={"Allow": "POST"},
        detail="Use POST /stream with JSON body: { msg, model?, provider?, session_id?, client_tz?, client_locale? }",
    )
