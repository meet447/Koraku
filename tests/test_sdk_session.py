"""Tests for KorakuSession multi-turn API."""
from __future__ import annotations

import asyncio

import pytest

from koraku import Koraku, KorakuConfig, KorakuSession
from koraku.core.models import SessionState


@pytest.mark.asyncio
async def test_session_send_then_stream_two_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    from koraku.agent import run as agent_run

    turn_messages: list[str] = []

    async def fake_run(self, user_input, session, emit, **kwargs):  # type: ignore[no-untyped-def]
        turn_messages.append(str(user_input))
        session.add_message("assistant", f"reply:{user_input}")
        ev = {"type": "agent.completed", "data": {"reason": "end_turn"}}
        emit(ev)
        yield ev

    monkeypatch.setattr(agent_run.Agent, "run", fake_run)

    koraku = Koraku(KorakuConfig())
    chat = koraku.session(session=SessionState(session_id="s-multi"))

    await chat.send("first")
    events = [e async for e in chat.stream()]
    assert events[-1]["type"] == "agent.completed"

    await chat.send("second")
    async for _ in chat.stream():
        pass

    assert turn_messages == ["first", "second"]
    assert len(chat.state.messages) == 2
    assert chat.state.messages[0].content == "reply:first"
    await chat.close()


@pytest.mark.asyncio
async def test_session_send_and_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    from koraku.agent import run as agent_run

    async def fake_run(self, user_input, session, emit, **kwargs):  # type: ignore[no-untyped-def]
        ev = {"type": "agent.completed", "data": {"reason": "end_turn"}}
        emit(ev)
        yield ev

    monkeypatch.setattr(agent_run.Agent, "run", fake_run)

    koraku = Koraku(KorakuConfig())
    async with koraku.session() as chat:
        events = [e async for e in chat.send_and_stream("hello")]
        assert events[-1]["type"] == "agent.completed"


@pytest.mark.asyncio
async def test_session_requires_send_before_stream() -> None:
    koraku = Koraku(KorakuConfig())
    chat = koraku.session()
    with pytest.raises(RuntimeError, match="send"):
        async for _ in chat.stream():
            pass
    await chat.close()


@pytest.mark.asyncio
async def test_session_context_manager_closes() -> None:
    koraku = Koraku(KorakuConfig())
    async with koraku.session() as chat:
        assert not chat.closed
    assert chat.closed
