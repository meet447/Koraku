"""Long-lived in-process chat sessions (V2-style send / stream)."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from koraku.agent.agent_definition import AgentDefinition
from koraku.agent.hooks import AgentHooks
from koraku.agent.permissions import PermissionMode
from koraku.agent.runtime_context import ExecutionTarget
from koraku.core.models import SessionState
from koraku.sdk_events import KorakuEvent

if TYPE_CHECKING:
    from koraku.sdk import Koraku


@dataclass
class KorakuSessionOptions:
    """Per-session overrides (inherit from the parent ``Koraku`` instance when unset)."""

    model: str | None = None
    provider: str | None = None
    workspace: str | None = None
    execution_target: ExecutionTarget | None = None
    permission_mode: PermissionMode | None = None
    hooks: AgentHooks | None = None
    agents: dict[str, AgentDefinition] | None = None


class KorakuSession:
    """Multi-turn conversation handle for the embeddable SDK.

    Claude Agent SDK V2-style usage::

        async with koraku.session() as chat:
            await chat.send("Hello")
            async for event in chat.stream():
                ...
            await chat.send("What did I just say?")
            async for event in chat.stream():
                ...

    Each ``send()`` + ``stream()`` pair runs one agent turn on the shared
    ``SessionState`` (conversation history persists across turns).
    """

    def __init__(
        self,
        koraku: Koraku,
        *,
        session: SessionState | None = None,
        session_id: str | None = None,
        options: KorakuSessionOptions | None = None,
    ) -> None:
        sid = (session.session_id if session else None) or session_id or str(uuid.uuid4())
        self._koraku = koraku
        self._state = session or SessionState(session_id=sid)
        self._options = options or KorakuSessionOptions()
        self._pending_message: str | None = None
        self._lock = asyncio.Lock()
        self._closed = False
        self._turn_cancel: asyncio.Event | None = None

    @property
    def session_id(self) -> str:
        return self._state.session_id

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def closed(self) -> bool:
        return self._closed

    async def send(self, message: str) -> None:
        """Queue the next user message. Call ``stream()`` to run the turn."""
        text = (message or "").strip()
        if not text:
            raise ValueError("message must be non-empty")
        if self._closed:
            raise RuntimeError("KorakuSession is closed")
        async with self._lock:
            if self._pending_message is not None:
                raise RuntimeError("Previous message has not been streamed yet; call stream() first")
            self._pending_message = text

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        """Yield agent events for the message passed to the latest ``send()``."""
        if self._closed:
            raise RuntimeError("KorakuSession is closed")
        async with self._lock:
            if self._pending_message is None:
                raise RuntimeError("Call send(message) before stream()")
            message = self._pending_message
            self._pending_message = None

        cancel = asyncio.Event()
        self._turn_cancel = cancel
        try:
            async for event in self._koraku.stream(
                message,
                session=self._state,
                session_id=self._state.session_id,
                model=self._options.model,
                provider=self._options.provider,
                workspace=self._options.workspace,
                execution_target=self._options.execution_target,
                cancel_event=cancel,
                permission_mode=self._options.permission_mode,
                hooks=self._options.hooks,
                agents=self._options.agents,
            ):
                yield event
        finally:
            self._turn_cancel = None

    async def stream_events(self) -> AsyncIterator[KorakuEvent]:
        """Like :meth:`stream`, but yields :class:`~koraku.sdk_events.KorakuEvent` wrappers."""
        async for raw in self.stream():
            yield KorakuEvent.wrap(raw)

    async def send_and_stream_events(self, message: str) -> AsyncIterator[KorakuEvent]:
        """Convenience helper: ``send`` then :meth:`stream_events`."""
        await self.send(message)
        async for event in self.stream_events():
            yield event

    async def send_and_stream(self, message: str) -> AsyncIterator[dict[str, Any]]:
        """Convenience helper: ``send`` then ``stream`` in one call."""
        await self.send(message)
        async for event in self.stream():
            yield event

    async def close(self) -> None:
        """Cancel an in-flight turn and prevent further sends."""
        self._closed = True
        if self._turn_cancel is not None and not self._turn_cancel.is_set():
            self._turn_cancel.set()

    async def __aenter__(self) -> KorakuSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
