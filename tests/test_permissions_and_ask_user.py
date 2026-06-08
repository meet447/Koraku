"""Tests for permission modes and AskUser validation."""
from __future__ import annotations

from koraku.agent.permissions import (
    filter_tools_for_permission_mode,
    normalize_permission_mode,
    tool_blocked_message,
)
from koraku.tools.ask_user import _validate_questions
from koraku.tools.tool_def import Tool


async def _noop(**kwargs: object) -> str:
    return "ok"


def _tool(name: str) -> Tool:
    return Tool(name=name, description=name, input_schema={"type": "object", "properties": {}}, handler=_noop)


def test_normalize_permission_mode_defaults_unknown():
    assert normalize_permission_mode(None) == "default"
    assert normalize_permission_mode("PLAN") == "plan"
    assert normalize_permission_mode("nope") == "default"


def test_filter_tools_plan_mode():
    tools = [_tool("AskUser"), _tool("Read"), _tool("Write"), _tool("Bash")]
    filtered = filter_tools_for_permission_mode(tools, "plan")
    names = {t.name for t in filtered}
    assert "AskUser" in names
    assert "Read" in names
    assert "Write" not in names


def test_tool_blocked_read_only():
    assert tool_blocked_message("Write", "read_only") is not None
    assert tool_blocked_message("Read", "read_only") is None


def test_validate_questions_requires_text():
    err = _validate_questions([{"header": "Tone", "options": [{"label": "Warm"}]}])
    assert isinstance(err, str)
    assert "question" in err.lower()


def test_validate_questions_ok():
    out = _validate_questions([
        {
            "header": "Tone",
            "question": "Which tone should I use?",
            "options": [{"label": "Warm", "description": "Friendly"}],
        }
    ])
    assert isinstance(out, list)
    assert out[0]["question"].startswith("Which tone")
