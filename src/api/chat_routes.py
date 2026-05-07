"""Chat UI API: model list + SSE ``/stream``."""
from __future__ import annotations

import asyncio
import contextlib
import json
from contextvars import Token
from typing import TYPE_CHECKING, Any, AsyncIterator, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from src.agent import _step_budget, get_or_create_chat_session
from src.agent.runtime_context import AgentRunContext, ChatExecutionMode
from src.api.linked_device import chat_local_execution_available
from src.agent.unconfigured import run_unconfigured
from src.core.auth_supabase import (
    SUPABASE_JWT_REQUEST_ERROR_MESSAGES,
    verify_supabase_jwt_bearer_detail,
)
from src.core.config import settings
from src.core.rate_limit import RateLimit, enforce_rate_limit, rate_limit_key
from src.integrations import composio as composio_runtime
from src.integrations.blaxel_runtime import (
    cloud_blaxel_block_reason,
    ensure_chat_sandbox,
    session_workspace_root_posix,
)
from src.integrations.cloud_user import (
    effective_cloud_user_id,
    reset_cloud_user_id,
    set_cloud_user_id,
)
from src.integrations.supabase_chat_history import hydrate_session_messages_from_db
from src.integrations.supabase_personalization import (
    fetch_personalization_sync,
    supabase_personalization_configured,
)
from src.llm.catalog import (
    configured_provider_ids,
    resolve_effective_model,
    ui_chat_models_async,
)
from src.streaming import KorakuStreamState, map_koraku_stream_events
from src.tools.registry import tools_for_execution_target
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


class StreamClientHistoryMessage(BaseModel):
    """One visible prior chat message sent by the browser as a hydration fallback."""

    role: Literal["user", "assistant"]
    text: str = Field(..., max_length=20_000)


class StreamChatBody(BaseModel):
    """JSON body for ``POST /stream`` (SSE response)."""

    msg: str = Field(default="", max_length=400_000)
    model: str = ""
    provider: str = ""
    session_id: str = ""
    client_tz: str | None = None
    client_locale: str | None = None
    images: list[StreamImagePart] = Field(default_factory=list, max_length=8)
    client_history: list[StreamClientHistoryMessage] = Field(default_factory=list, max_length=40)
    execution_target: ChatExecutionMode = "cloud"

    @field_validator("execution_target", mode="before")
    @classmethod
    def _coerce_execution_target(cls, v: object) -> str:
        """Only ``cloud`` and ``local``; legacy ``server`` / unknown values → ``cloud``."""
        if not isinstance(v, str):
            return "cloud"
        s = v.strip().lower()
        if s == "local":
            return "local"
        return "cloud"

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


async def _yield_error_events(error_msg: str, stream_state: KorakuStreamState) -> AsyncIterator[str]:
    for row in map_koraku_stream_events({"type": "agent.error", "data": {"error": error_msg}}, stream_state):
        yield format_sse(row)
        await asyncio.sleep(0)


async def _provision_cloud_sandbox(session_id: str) -> tuple[Any | None, str | None]:
    block = cloud_blaxel_block_reason(settings)
    if block:
        return None, block
    try:
        ready_timeout = max(5.0, float(settings.blaxel_sandbox_ready_timeout_seconds))
        cloud_sandbox = await asyncio.wait_for(
            ensure_chat_sandbox(
                session_id,
                settings,
                user_id=effective_cloud_user_id(),
            ),
            timeout=ready_timeout,
        )
        return cloud_sandbox, None
    except asyncio.TimeoutError:
        t = int(ready_timeout)
        err = (
            f"Blaxel sandbox did not become ready within {t}s. "
            "Check BL_WORKSPACE, BL_API_KEY, and Blaxel service status."
        )
        return None, err
    except Exception as e:
        return None, f"Blaxel sandbox: {e}"


async def _yield_sse_events_from_queue(
    queue: asyncio.Queue[dict | None],
    task: asyncio.Task,
    stream_state: KorakuStreamState,
) -> AsyncIterator[str]:
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


def _resolve_stream_provider_model(model: str, provider: str) -> tuple[str, str]:
    active = (settings.llm_provider or "fireworks").strip().lower()
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
    execution_target: ChatExecutionMode,
    agent: "Agent | None",
    server_mode: str,
    auth_sub: str | None = None,
    client_history: list[StreamClientHistoryMessage] | None = None,
    request: Request | None = None,
    cancel_event: asyncio.Event | None = None,
    stream_run_id: str | None = None,
) -> AsyncIterator[str]:
    session = get_or_create_chat_session(session_id)
    account_p: dict[str, str] | None = None
    if auth_sub and supabase_personalization_configured():
        fetched = await asyncio.to_thread(fetch_personalization_sync, auth_sub)
        account_p = fetched if fetched is not None else {"agent_name": "", "memory": "", "soul": ""}
    hydration = await hydrate_session_messages_from_db(
        session,
        incoming_user_text=msg.strip(),
        auth_sub=auth_sub,
        client_history=[p.model_dump() for p in (client_history or [])],
    )
    eff_provider, resolved_model = _resolve_stream_provider_model(model, provider)

    stream_state = KorakuStreamState()
    if stream_run_id and str(stream_run_id).strip():
        stream_state.run_id = str(stream_run_id).strip()
    stream_state.resolved_model = resolved_model if server_mode == "live" else "koraku-unconfigured"
    stream_state.eff_provider = eff_provider if server_mode == "live" else "unconfigured"

    eff_cancel: asyncio.Event | None = cancel_event
    watch_disconnect: asyncio.Task[None] | None = None
    if request is not None:
        eff_cancel = cancel_event or asyncio.Event()

        async def _disconnect_watcher() -> None:
            try:
                while True:
                    if await request.is_disconnected():
                        eff_cancel.set()
                        return
                    await asyncio.sleep(0.3)
            except asyncio.CancelledError:
                return

        watch_disconnect = asyncio.create_task(_disconnect_watcher())

    async def _stop_disconnect_watch() -> None:
        if watch_disconnect is not None:
            watch_disconnect.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watch_disconnect

    # Flush preamble first so the client shows activity; Blaxel provisioning can be slow.
    yield format_sse(
        stream_state.started_payload(stream_state.resolved_model, chat_session_id=session.session_id)
    )
    await asyncio.sleep(0)
    yield format_sse(stream_state.s2_stream_payload())
    await asyncio.sleep(0)
    yield format_sse(stream_state.route_decision_payload())
    await asyncio.sleep(0)

    cloud_sandbox = None
    if execution_target == "cloud":
        cloud_sandbox, err = await _provision_cloud_sandbox(session.session_id)
        if err:
            async for chunk in _yield_error_events(err, stream_state):
                yield chunk
            await _stop_disconnect_watch()
            yield "event: done\n\n"
            return

    budget = msg.strip() or ("[images]" if images else "")
    mode_hint, max_steps_hint = _step_budget(budget)
    tz = _normalize_client_hint(client_tz)
    loc = _normalize_client_hint(client_locale)
    blaxel_on = cloud_sandbox is not None
    koraku_boot = {
        "workspace_session_id": session.session_id,
        "runId": stream_state.run_id,
        "server_mode": server_mode,
        "mode": mode_hint,
        "max_steps": max_steps_hint,
        "execution_target": execution_target,
        "blaxel_sandbox": blaxel_on,
        "tool_names": [
            t.name for t in tools_for_execution_target(execution_target, blaxel_sandbox_active=blaxel_on)
        ],
        "provider": stream_state.eff_provider,
        "model": stream_state.resolved_model,
        "client_timezone": tz,
        "client_locale": loc,
    }
    init_cwd = workspace_dir()
    if execution_target == "cloud" and cloud_sandbox is not None:
        init_cwd = session_workspace_root_posix(
            effective_cloud_user_id(),
            session.session_id,
            settings,
        )
    yield format_sse(stream_state.system_init_payload(init_cwd, koraku_boot))
    await asyncio.sleep(0)
    for row in map_koraku_stream_events({"type": "agent.history", "data": hydration.to_trace_data()}, stream_state):
        yield format_sse(row)
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
                    model=model,
                    provider=provider,
                    client_timezone=tz,
                    client_locale=loc,
                    image_parts=img_payload,
                    run_context=AgentRunContext(execution_target=execution_target),
                    cloud_sandbox=cloud_sandbox,
                    account_personalization=account_p,
                    run_id=stream_state.run_id,
                    cancel_event=eff_cancel,
                )
            )
            async for _ in agent_iter:
                pass
        except Exception as e:
            emit({"type": "agent.error", "data": {"error": str(e)}})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(run_agent())

    async for chunk in _yield_sse_events_from_queue(queue, task, stream_state):
        yield chunk

    await task

    await _stop_disconnect_watch()
    yield "event: done\n\n"


@router.get("/api/chat-models")
async def chat_models():
    """Model IDs for the chat UI dropdown (per provider + optional CHAT_MODEL_OPTIONS)."""
    return await ui_chat_models_async()


@router.post("/stream")
async def stream_endpoint_post(body: StreamChatBody, request: Request):
    """SSE streaming agent chat. Use JSON body (large prompts); response is ``text/event-stream``."""
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    auth_result = verify_supabase_jwt_bearer_detail(auth_header)
    auth_sub = auth_result.sub
    if settings.require_auth_for_chat and not auth_result.ok:
        raise HTTPException(
            status_code=401,
            detail=SUPABASE_JWT_REQUEST_ERROR_MESSAGES.get(auth_result.reason, "Authorization required."),
        )
    enforce_rate_limit(
        RateLimit(
            key=rate_limit_key(request, scope="chat-stream", user_id=auth_sub),
            limit=settings.chat_rate_limit_per_minute,
        )
    )

    if body.execution_target == "local":
        if not chat_local_execution_available(request):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Local runs use your linked Koraku desktop app. None is linked for this "
                    "session — use cloud, or install and pair the desktop app."
                ),
            )
        raise HTTPException(
            status_code=501,
            detail="Routing chat to your linked desktop is not implemented yet.",
        )
    agent = getattr(request.app.state, "koraku_agent", None)
    server_mode = getattr(request.app.state, "server_mode", "unconfigured")

    async def event_generator() -> AsyncIterator[str]:
        composio_token: Token | None = None
        cloud_token: Token | None = None
        try:
            if auth_sub:
                composio_token = composio_runtime.set_composio_request_user(auth_sub)
                cloud_token = set_cloud_user_id(auth_sub)
            async for chunk in _stream_agent_sse(
                body.msg.strip(),
                images=body.images,
                model=body.model,
                provider=body.provider,
                session_id=(body.session_id.strip() or None),
                client_tz=body.client_tz,
                client_locale=body.client_locale,
                execution_target=body.execution_target,
                agent=agent,
                server_mode=server_mode,
                auth_sub=auth_sub,
                client_history=body.client_history,
                request=request,
            ):
                yield chunk
        finally:
            composio_runtime.reset_composio_request_user(composio_token)
            reset_cloud_user_id(cloud_token)

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
        detail=(
            "Use POST /stream with JSON body: { msg, model?, provider?, session_id?, client_tz?, "
            "client_locale?, execution_target?: 'cloud'|'local' (local requires a linked desktop app) }"
        ),
    )
