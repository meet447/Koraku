"""Tests for sdk_events helpers and KorakuConfig.from_env."""
from __future__ import annotations

import asyncio

import pytest

from koraku import EventType, Koraku, KorakuConfig, KorakuEvent, collect_assistant_text, is_completed, parse_event
from koraku.sdk_events import assistant_text_blocks


def test_event_type_namespace() -> None:
    assert EventType.agent.completed == "agent.completed"
    assert EventType.agent.question == "agent.question"
    assert EventType.stream_event == "stream_event"


def test_koraku_event_wrap_and_match() -> None:
    raw = {"type": "agent.completed", "data": {"reason": "end_turn", "steps": 2}}
    event = parse_event(raw)
    assert event.type == EventType.agent.completed
    assert event.matches(EventType.agent.completed)
    assert event.is_completed
    assert event.data["steps"] == 2
    assert event.raw is raw


def test_koraku_event_question_fields() -> None:
    event = KorakuEvent.wrap({
        "type": "agent.question",
        "data": {
            "interaction_id": "q-1",
            "questions": [{"header": "Goal", "question": "What for?", "options": [{"label": "Work"}]}],
        },
    })
    assert event.is_question
    assert event.interaction_id == "q-1"
    assert len(event.questions) == 1


def test_koraku_stream_events_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = {"type": "agent.completed", "data": {"reason": "test"}}

    async def fake_run(self, user_input, session, emit, **kwargs):  # type: ignore[no-untyped-def]
        emit(completed)
        yield completed

    from koraku.agent import run as agent_run

    monkeypatch.setattr(agent_run.Agent, "run", fake_run)

    agent = Koraku(KorakuConfig(fireworks_api_key="test-key"))

    async def _collect() -> list[KorakuEvent]:
        return [e async for e in agent.stream_events("hi")]

    events = asyncio.run(_collect())
    assert len(events) == 1
    assert events[0].type == EventType.agent.completed


def test_assistant_text_blocks_from_message() -> None:
    event = {
        "type": "stream_event",
        "event": {
            "type": "assistant_message",
            "message": {
                "content": [{"type": "text", "text": "Hello"}],
            },
        },
    }
    assert collect_assistant_text([event]) == "Hello"


def test_is_completed() -> None:
    assert is_completed({"type": "agent.completed", "data": {}})
    assert not is_completed({"type": "stream_event", "event": {}})


def test_is_action_and_run_log() -> None:
    from koraku.sdk_events import is_action, is_run_log, run_log_path

    assert is_action({"type": "agent.action", "data": {"action_id": "a1"}})
    assert is_run_log({"type": "agent.run_log", "data": {"path": "/tmp/runs/x"}})
    assert run_log_path({"type": "agent.run_log", "data": {"path": "/tmp/runs/x"}}) == "/tmp/runs/x"


def test_assistant_text_blocks_delta() -> None:
    event = {
        "type": "stream_event",
        "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}},
    }
    assert assistant_text_blocks(event) == ["Hi"]


def test_koraku_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("MAX_STEPS", "9")
    cfg = KorakuConfig.from_env()
    assert cfg.llm_provider == "anthropic"
    assert cfg.anthropic_api_key == "test-key"
    assert cfg.max_steps == 9


def test_koraku_config_from_env_overrides() -> None:
    cfg = KorakuConfig.from_env(workspace="/tmp/ws", max_steps=3)
    assert cfg.workspace == "/tmp/ws"
    assert cfg.max_steps == 3
