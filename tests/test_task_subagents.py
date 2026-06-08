"""Tests for Task subagent definitions and tool resolution."""
from __future__ import annotations

from koraku.agent.agent_definition import AgentDefinition
from koraku.agent.delegation import _resolve_agent_definition, _tools_for_task_subagent
from koraku.tools.tool_def import Tool


async def _noop(**kwargs: object) -> str:
    return "ok"


def _tool(name: str) -> Tool:
    return Tool(name=name, description=name, input_schema={"type": "object", "properties": {}}, handler=_noop)


def test_resolve_agent_definition_case_insensitive():
    agents = {
        "researcher": AgentDefinition(description="Finds facts", prompt="You research."),
    }
    assert _resolve_agent_definition(agents, "Researcher") is not None
    assert _resolve_agent_definition(agents, "missing") is None


def test_tools_for_task_subagent_respects_definition_list():
    definition = AgentDefinition(
        description="Reads files",
        prompt="Read only.",
        tools=("Read", "Glob"),
    )
    pool = [_tool("Read"), _tool("Glob"), _tool("Write"), _tool("Task")]
    # monkeypatch tools_for_execution_target by calling helper internals via fake - 
    # _tools_for_task_subagent calls tools_for_execution_target; use integration style:
    from koraku.tools.registry import tools_for_execution_target

    base = tools_for_execution_target("local", blaxel_sandbox_active=False)
    names = {t.name for t in base}
    assert "Read" in names
    resolved = _tools_for_task_subagent(
        definition=definition,
        execution_target="local",
        blaxel_sandbox_active=False,
        allow_task=False,
    )
    resolved_names = {t.name for t in resolved}
    assert "Read" in resolved_names
    assert "Glob" in resolved_names
    assert "Write" not in resolved_names
    assert "Task" not in resolved_names
