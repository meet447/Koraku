"""Await user answers and tool approvals during an agent run."""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 600.0


@dataclass
class _PendingEntry:
    kind: str
    future: asyncio.Future[dict[str, Any]]
    run_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


_lock = asyncio.Lock()
_pending: dict[str, _PendingEntry] = {}


def new_interaction_id() -> str:
    return str(uuid.uuid4())


async def register(kind: str, *, run_id: str | None = None, payload: dict[str, Any] | None = None) -> tuple[str, asyncio.Future[dict[str, Any]]]:
    interaction_id = new_interaction_id()
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    entry = _PendingEntry(kind=kind, future=future, run_id=run_id, payload=dict(payload or {}))
    async with _lock:
        _pending[interaction_id] = entry
    return interaction_id, future


async def resolve(interaction_id: str, body: dict[str, Any]) -> bool:
    async with _lock:
        entry = _pending.pop(interaction_id, None)
    if entry is None or entry.future.done():
        return False
    if not entry.future.done():
        entry.future.set_result(dict(body))
    return True


async def cancel(interaction_id: str, *, reason: str = "cancelled") -> None:
    async with _lock:
        entry = _pending.pop(interaction_id, None)
    if entry is None or entry.future.done():
        return
    entry.future.set_exception(asyncio.TimeoutError(reason))


async def cancel_run(run_id: str, *, reason: str = "run_ended") -> None:
    if not run_id:
        return
    async with _lock:
        ids = [iid for iid, entry in _pending.items() if entry.run_id == run_id]
        entries = [(iid, _pending.pop(iid)) for iid in ids]
    for _iid, entry in entries:
        if not entry.future.done():
            entry.future.set_exception(asyncio.TimeoutError(reason))


async def wait_for_response(
    interaction_id: str,
    future: asyncio.Future[dict[str, Any]],
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        return await asyncio.wait_for(asyncio.shield(future), timeout=max(1.0, timeout_seconds))
    except asyncio.TimeoutError:
        await cancel(interaction_id, reason="timeout")
        raise
    finally:
        async with _lock:
            _pending.pop(interaction_id, None)


def respond_to_interaction(interaction_id: str, body: dict[str, Any]) -> bool:
    """Sync helper for in-process embedders (schedules resolve on the running loop)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    loop.create_task(resolve(interaction_id, body))
    return True
