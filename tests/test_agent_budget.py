"""Agent harness budgets and Composio goal classification."""
from __future__ import annotations

from koraku.agent.budget import (
    LoopTracker,
    classify_composio_goal,
    classify_turn_task,
    composio_max_rounds_for_goal,
    resolve_turn_limits,
    tools_for_composio_worker,
)
from koraku.tools.tool_def import Tool


def _fake_tool(name: str) -> Tool:
    return Tool(name=name, description=name, input_schema={"type": "object", "properties": {}}, handler=lambda **_: "")


def test_classify_turn_task_standard() -> None:
    assert classify_turn_task("check my gmail and mark as read") == "standard"
    assert classify_turn_task("hello there") == "standard"
    assert (
        classify_turn_task("whats the latest news related to re neet site being hacked")
        == "standard"
    )


def test_classify_turn_task_research() -> None:
    assert classify_turn_task("research the best pricing for " + "x " * 30) == "research"


def test_classify_composio_goal_simple() -> None:
    assert classify_composio_goal("List unread Gmail and mark all as read") == "integration_simple"


def test_classify_composio_goal_compose() -> None:
    assert classify_composio_goal("Draft a reply to the latest thread") == "integration_compose"


def test_composio_simple_fewer_rounds() -> None:
    simple = composio_max_rounds_for_goal("mark inbox as read")
    full = composio_max_rounds_for_goal(
        "Investigate every label in the account and produce a full audit spreadsheet"
    )
    assert simple < full


def test_tools_for_composio_worker_simple_is_composio_only() -> None:
    base = [_fake_tool("WebSearch"), _fake_tool("TodoWrite")]
    comp = [_fake_tool("GMAIL_FETCH_EMAILS")]
    out = tools_for_composio_worker(base, comp, "check unread email")
    assert [t.name for t in out] == ["GMAIL_FETCH_EMAILS"]


def test_loop_tracker_detects_repeat() -> None:
    tr = LoopTracker()
    tu = {"name": "GMAIL_FETCH", "input": {"max_results": 5}}
    tr.record([tu])
    assert not tr.has_repeat()
    tr.record([tu])
    assert tr.has_repeat()


def test_resolve_turn_limits_standard_for_chat() -> None:
    mode, limits = resolve_turn_limits("any unread in my inbox?", None)
    assert mode == "standard"
    assert limits.task_class == "standard"
    assert limits.max_rounds >= 10
