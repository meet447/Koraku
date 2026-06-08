"""Propose one-click UI actions the user can execute from chat."""
from __future__ import annotations

import json
from typing import Any

from koraku.actions.pending_actions import register_action
from koraku.agent.active_run import get_active_run_id, get_active_session_id
from koraku.agent.active_run import get_active_emit


async def _propose_action(**kwargs: Any) -> str:
    label = str(kwargs.get("label") or "").strip()
    tool_name = str(kwargs.get("tool") or kwargs.get("tool_name") or "").strip()
    if not label or not tool_name:
        return "Error: label and tool are required."
    description = str(kwargs.get("description") or "").strip()
    tool_input = kwargs.get("input") if isinstance(kwargs.get("input"), dict) else {}
    action_id = register_action(
        label=label,
        description=description,
        tool_name=tool_name,
        tool_input=tool_input,
        run_id=get_active_run_id(),
        session_id=get_active_session_id(),
    )
    payload = {
        "action_id": action_id,
        "label": label,
        "description": description,
        "tool": tool_name,
        "input": tool_input,
        "run_id": get_active_run_id() or "",
    }
    emit = get_active_emit()
    if emit is not None:
        emit({"type": "agent.action", "data": payload})
    return json.dumps(
        {
            "ok": True,
            "action_id": action_id,
            "message": "Action proposed — the user can click to execute it in the UI.",
        },
        indent=2,
    )


def build_propose_action_tool() -> Any:
    from koraku.tools.tool_def import Tool

    return Tool(
        name="ProposeAction",
        description=(
            "Propose a one-click action card for the user (label + tool + input). "
            "Use when a concrete next step can be executed with one tap instead of more chat."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Short button label"},
                "description": {"type": "string", "description": "Optional longer explanation"},
                "tool": {"type": "string", "description": "Registered tool name to run on click"},
                "input": {
                    "type": "object",
                    "description": "Tool arguments when the user clicks the action",
                },
            },
            "required": ["label", "tool"],
        },
        handler=_propose_action,
        categories=["ui"],
    )
