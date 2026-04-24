"""Background agent runs with SSE subscribe + replay (disconnect does not cancel the run)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextvars import Token
from typing import TYPE_CHECKING, Any, AsyncIterator, cast

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.api.chat_routes import StreamChatBody, _stream_agent_sse, format_sse
from src.api.linked_device import chat_local_execution_available
from src.core.auth_supabase import verify_supabase_jwt_bearer
from src.integrations import composio as composio_runtime
from src.integrations.cloud_user import reset_cloud_user_id, set_cloud_user_id
from src.integrations.upstash_redis import (
    detached_run_append_chunk,
    detached_run_create,
    detached_run_delete,
    detached_run_exists,
    detached_run_allows,
    detached_run_finish,
    detached_run_is_done,
    detached_run_llen,
    detached_run_lrange_all,
    detached_run_lrange_slice,
    detached_run_owner_sub,
    upstash_redis_configured,
)

if TYPE_CHECKING:
    from src.agent import Agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# After a run finishes, drop its in-memory buffer (override in tests via monkeypatch).
_DETACHED_GC_SEC = float((os.environ.get("KORAKU_DETACHED_RUN_GC_SECONDS") or "600").strip() or "600")

# Max buffered SSE chunks per run (memory cap; older runs should finish or be GC'd).
_MAX_CHUNKS_PER_RUN = 12_000

_SENTINEL: object = object()


def _use_redis_detached() -> bool:
    return upstash_redis_configured()


def _parse_detached_event(raw: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    try:
        seq = int(obj.get("seq", -1))
    except (TypeError, ValueError):
        return None
    chunk = obj.get("chunk")
    if not isinstance(chunk, str):
        return None
    return {"seq": seq, "chunk": chunk}


class RedisDetachedRunBuffer:
    """Redis-backed SSE buffer (Upstash REST); same append/finish/subscribe contract as ``_RunBuffer``."""

    __slots__ = ("run_id",)

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    async def append(self, raw_chunk: str) -> None:
        await detached_run_append_chunk(self.run_id, raw_chunk)

    async def finish(self) -> None:
        await detached_run_finish(self.run_id)

    async def subscribe(self, after: int) -> AsyncIterator[str]:
        # Tighter poll when tailing Redis (detached mode); still slower than direct ``/stream``.
        poll_interval = 0.012
        items = await detached_run_lrange_all(self.run_id)
        last_seq = after
        for raw in items:
            ev = _parse_detached_event(raw)
            if ev is None:
                continue
            seq, chunk = ev["seq"], ev["chunk"]
            if seq > last_seq:
                yield chunk
                last_seq = seq
                if "event: done" in chunk:
                    return

        seen = len(items)
        while True:
            length = await detached_run_llen(self.run_id)
            if length > seen:
                rows = await detached_run_lrange_slice(self.run_id, seen, length - 1)
                for raw in rows:
                    ev = _parse_detached_event(raw)
                    if ev is None:
                        continue
                    seq, chunk = ev["seq"], ev["chunk"]
                    if seq > last_seq:
                        yield chunk
                        last_seq = seq
                        if "event: done" in chunk:
                            return
                seen = length
            elif await detached_run_is_done(self.run_id):
                return
            await asyncio.sleep(poll_interval)


class _RunBuffer:
    __slots__ = (
        "owner_sub",
        "chunks",
        "next_seq",
        "done",
        "lock",
        "subscribers",
    )

    def __init__(self, owner_sub: str | None) -> None:
        self.owner_sub = owner_sub
        self.chunks: list[tuple[int, str]] = []
        self.next_seq = 0
        self.done = False
        self.lock = asyncio.Lock()
        self.subscribers: list[asyncio.Queue[Any]] = []

    def allows(self, auth_sub: str | None) -> bool:
        if self.owner_sub is None:
            return True
        return auth_sub == self.owner_sub

    async def append(self, raw_chunk: str) -> None:
        async with self.lock:
            if self.done:
                return
            seq = self.next_seq
            self.next_seq += 1
            if raw_chunk.startswith("id: "):
                wrapped = raw_chunk
            else:
                wrapped = f"id: {seq}\n{raw_chunk}"
            self.chunks.append((seq, wrapped))
            if len(self.chunks) > _MAX_CHUNKS_PER_RUN:
                self.chunks.pop(0)
            subs = list(self.subscribers)
        # Await puts so the agent is back-pressured if the HTTP client is slow (never drop chunks).
        for q in subs:
            await q.put(wrapped)

    async def finish(self) -> None:
        async with self.lock:
            self.done = True
            subs = list(self.subscribers)
            self.subscribers.clear()
        for q in subs:
            try:
                await q.put(_SENTINEL)
            except Exception:
                pass

    async def subscribe(self, after: int) -> AsyncIterator[str]:
        # Unbounded: delivery is bounded by ``_MAX_CHUNKS_PER_RUN`` on the replay list; slow clients
        # apply backpressure via ``await q.put`` in ``append`` instead of dropping events.
        q: asyncio.Queue[Any] = asyncio.Queue()
        try:
            async with self.lock:
                is_done = self.done
                if not is_done:
                    self.subscribers.append(q)
                replay = [(s, w) for s, w in self.chunks if s > after]
            for _, w in replay:
                yield w
            if is_done:
                return
            while True:
                item = await q.get()
                if item is _SENTINEL:
                    break
                yield item
        finally:
            async with self.lock:
                try:
                    self.subscribers.remove(q)
                except ValueError:
                    pass


_registry: dict[str, _RunBuffer] = {}
_registry_lock = asyncio.Lock()


async def _schedule_gc(run_id: str) -> None:
    await asyncio.sleep(_DETACHED_GC_SEC)
    if _use_redis_detached():
        await detached_run_delete(run_id)
    else:
        async with _registry_lock:
            _registry.pop(run_id, None)


async def _run_worker(
    run_id: str,
    body: StreamChatBody,
    auth_sub: str | None,
    agent: Agent | None,
    server_mode: str,
) -> None:
    if _use_redis_detached():
        buf: _RunBuffer | RedisDetachedRunBuffer = RedisDetachedRunBuffer(run_id)
    else:
        b = _registry.get(run_id)
        if b is None:
            return
        buf = b

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
            agent=cast(Any, agent),
            server_mode=server_mode,
            auth_sub=auth_sub,
        ):
            await buf.append(chunk)
    except Exception as e:
        logger.exception("detached run worker failed: %s", e)
        await buf.append(format_sse({"type": "agent.error", "data": {"error": str(e)}}))
        await buf.append("event: done\n\n")
    finally:
        composio_runtime.reset_composio_request_user(composio_token)
        reset_cloud_user_id(cloud_token)
        await buf.finish()
        asyncio.create_task(_schedule_gc(run_id), name=f"gc-detached-run-{run_id}")


@router.post("/runs")
async def start_detached_run(body: StreamChatBody, request: Request) -> JSONResponse:
    """Start an agent run in the background; subscribe with ``GET /runs/{run_id}/stream``."""
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    auth_sub = verify_supabase_jwt_bearer(auth_header)

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
    run_id = str(uuid.uuid4())
    if _use_redis_detached():
        await detached_run_create(run_id, auth_sub)
    else:
        buf = _RunBuffer(owner_sub=auth_sub)
        async with _registry_lock:
            _registry[run_id] = buf

    asyncio.create_task(
        _run_worker(run_id, body, auth_sub, agent, server_mode),
        name=f"koraku-detached-{run_id}",
    )
    return JSONResponse({"run_id": run_id})


@router.get("/runs/{run_id}/stream")
async def stream_detached_run(
    run_id: str,
    request: Request,
    after: int = Query(-1, ge=-1, description="Replay chunks with SSE id greater than this value."),
) -> StreamingResponse:
    """SSE replay + live tail for a detached run (browser may disconnect; run continues)."""
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    auth_sub = verify_supabase_jwt_bearer(auth_header)

    if _use_redis_detached():
        if not await detached_run_exists(run_id):
            raise HTTPException(status_code=404, detail="Unknown or expired run_id")
        if not await detached_run_allows(run_id, auth_sub):
            owner = await detached_run_owner_sub(run_id)
            if owner and auth_sub is None:
                raise HTTPException(
                    status_code=401,
                    detail="Authorization required to subscribe to this run.",
                )
            raise HTTPException(status_code=403, detail="This run belongs to another user")
        buf: _RunBuffer | RedisDetachedRunBuffer = RedisDetachedRunBuffer(run_id)
    else:
        async with _registry_lock:
            buf = _registry.get(run_id)
        if buf is None:
            raise HTTPException(status_code=404, detail="Unknown or expired run_id")

        if not buf.allows(auth_sub):
            if buf.owner_sub and auth_sub is None:
                raise HTTPException(
                    status_code=401,
                    detail="Authorization required to subscribe to this run.",
                )
            raise HTTPException(status_code=403, detail="This run belongs to another user")

    hdr_after = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
    if hdr_after is not None and str(hdr_after).strip().isdigit():
        after = max(after, int(str(hdr_after).strip()))

    async def gen() -> AsyncIterator[str]:
        try:
            async for chunk in buf.subscribe(after):
                yield chunk
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
