"""In-flight one-click action cards proposed by the agent."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

_pending: dict[str, _PendingAction] = {}


@dataclass
class _PendingAction:
    label: str
    description: str
    tool_name: str
    tool_input: dict[str, Any]
    run_id: str | None = None
    session_id: str | None = None
    executed: bool = field(default=False)


def register_action(
    *,
    label: str,
    description: str,
    tool_name: str,
    tool_input: dict[str, Any],
    run_id: str | None = None,
    session_id: str | None = None,
    action_id: str | None = None,
) -> str:
    aid = (action_id or "").strip() or str(uuid.uuid4())
    _pending[aid] = _PendingAction(
        label=label.strip(),
        description=description.strip(),
        tool_name=tool_name.strip(),
        tool_input=dict(tool_input or {}),
        run_id=run_id,
        session_id=session_id,
    )
    return aid


def get_action(action_id: str) -> _PendingAction | None:
    return _pending.get((action_id or "").strip())


async def execute_action(action_id: str, *, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = get_action(action_id)
    if entry is None:
        return {"ok": False, "error": "not_found"}
    if entry.executed:
        return {"ok": False, "error": "already_executed"}
    tool_input = dict(entry.tool_input)
    if overrides:
        tool_input.update(overrides)
    from koraku.tools.registry import get_tool

    tool = get_tool(entry.tool_name)
    if tool is None:
        return {"ok": False, "error": f"tool_not_found:{entry.tool_name}"}
    try:
        result = await asyncio.wait_for(tool.run(**tool_input), timeout=120.0)
    except asyncio.TimeoutError:
        return {"ok": False, "error": "tool_timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    entry.executed = True
    return {
        "ok": True,
        "action_id": action_id,
        "tool": entry.tool_name,
        "result": result,
    }
