"""Tests for sdk_events helpers and KorakuConfig.from_env."""
from __future__ import annotations

import pytest

from koraku import KorakuConfig, collect_assistant_text, is_completed
from koraku.sdk_events import assistant_text_blocks


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
