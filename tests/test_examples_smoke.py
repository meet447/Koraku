"""Smoke tests for example scripts (mocked LLM — no API keys required)."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

from koraku import EventType, Koraku, KorakuConfig, KorakuEvent

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _load_example_module(name: str):
    path = EXAMPLES_DIR / name
    spec = importlib.util.spec_from_file_location(f"example_{name.replace('.py', '')}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_MOCK_RAW_EVENTS = [
    {
        "type": "stream_event",
        "event": {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "ok"},
        },
    },
    {
        "type": "stream_event",
        "event": {
            "type": "assistant_message",
            "message": {"content": [{"type": "text", "text": "ok"}]},
        },
    },
    {
        "type": "agent.completed",
        "data": {"reason": "end_turn", "steps": 1},
    },
]


@pytest.fixture
def mock_stream_events(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(self, message, **kwargs):  # type: ignore[no-untyped-def]
        for event in _MOCK_RAW_EVENTS:
            yield event

    async def fake_stream_events(self, message, **kwargs):  # type: ignore[no-untyped-def]
        for event in _MOCK_RAW_EVENTS:
            yield KorakuEvent.wrap(event)

    async def fake_stream_text(self, message, **kwargs):  # type: ignore[no-untyped-def]
        return "ok"

    monkeypatch.setattr(Koraku, "stream", fake_stream)
    monkeypatch.setattr(Koraku, "stream_events", fake_stream_events)
    monkeypatch.setattr(Koraku, "stream_text", fake_stream_text)


@pytest.mark.parametrize(
    "name",
    [
        "from_env.py",
        "embed_python.py",
        "multi_turn_session.py",
        "llm_providers.py",
        "stream_events_tour.py",
        "custom_tool.py",
        "agent_hooks.py",
        "tool_approval.py",
        "ask_user.py",
    ],
)
def test_example_main_runs_mocked(name: str, monkeypatch: pytest.MonkeyPatch, mock_stream_events: None) -> None:
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER", "fireworks")
    mod = _load_example_module(name)
    asyncio.run(mod.main())
