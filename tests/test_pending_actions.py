"""One-click action cards."""
from __future__ import annotations

import pytest

from koraku.actions.pending_actions import execute_action, register_action


@pytest.mark.asyncio
async def test_register_and_execute_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from koraku.tools.tool_def import Tool
    import koraku.tools.registry as reg

    async def _echo(**kwargs):
        return f"ok:{kwargs.get('x')}"

    tool = Tool(
        name="EchoTestAction",
        description="test",
        input_schema={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
        handler=_echo,
    )
    original = reg.get_tool
    monkeypatch.setattr(reg, "get_tool", lambda name: tool if name == "EchoTestAction" else original(name))

    aid = register_action(
        label="Echo",
        description="echo x",
        tool_name="EchoTestAction",
        tool_input={"x": "hi"},
    )
    result = await execute_action(aid)
    assert result["ok"] is True
    assert "ok:hi" in str(result.get("result"))
    again = await execute_action(aid)
    assert again.get("error") == "already_executed"
