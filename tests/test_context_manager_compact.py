"""ContextManager: optional compaction of tool rounds for LLM context."""

from __future__ import annotations

from src.agent.context_manager import ContextManager
from src.core.models import AgentMessage


def test_compact_drops_completed_tool_pair_before_final_text() -> None:
    msgs = [
        AgentMessage(role="user", content=[{"type": "text", "text": "read foo"}]),
        AgentMessage(
            role="assistant",
            content=[{"type": "tool_use", "name": "Read", "id": "t1", "input": {"path": "foo"}}],
        ),
        AgentMessage(
            role="user",
            content=[{"type": "tool_result", "tool_use_id": "t1", "content": "file contents"}],
        ),
        AgentMessage(role="assistant", content=[{"type": "text", "text": "Here is what foo says."}]),
    ]
    cm = ContextManager(compact_tool_rounds=True)
    out = cm.process_messages(msgs)
    roles = [m.role for m in out]
    assert roles == ["user", "assistant"]
    assert out[0].content[0]["text"] == "read foo"  # type: ignore[index]
    assert "foo says" in out[1].content[0]["text"]  # type: ignore[index]


def test_compact_keeps_trailing_open_tool_round() -> None:
    msgs = [
        AgentMessage(role="user", content=[{"type": "text", "text": "go"}]),
        AgentMessage(
            role="assistant",
            content=[{"type": "tool_use", "name": "Read", "id": "t1", "input": {}}],
        ),
        AgentMessage(
            role="user",
            content=[{"type": "tool_result", "tool_use_id": "t1", "content": "x"}],
        ),
    ]
    cm = ContextManager(compact_tool_rounds=True)
    out = cm.process_messages(msgs)
    assert len(out) == 3


def test_compact_disabled_keeps_tool_pairs() -> None:
    msgs = [
        AgentMessage(role="user", content=[{"type": "text", "text": "q"}]),
        AgentMessage(
            role="assistant",
            content=[{"type": "tool_use", "name": "Read", "id": "t1", "input": {}}],
        ),
        AgentMessage(
            role="user",
            content=[{"type": "tool_result", "tool_use_id": "t1", "content": "x"}],
        ),
        AgentMessage(role="assistant", content=[{"type": "text", "text": "a"}]),
    ]
    cm = ContextManager(compact_tool_rounds=False)
    out = cm.process_messages(msgs)
    assert len(out) == 4
