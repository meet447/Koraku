"""**Task** — spawn a named subagent with its own prompt and tool subset."""
from __future__ import annotations

from koraku.agent.task_delegate_context import get_task_delegate_context
from koraku.tools.tool_def import Tool


async def _task_handler(agent: str, prompt: str, max_steps: int | None = None) -> str:
    ctx = get_task_delegate_context()
    if ctx is None:
        return "Error: Task is only available during an active chat turn with configured subagents."
    parent = ctx.agent
    fn = getattr(parent, "_execute_task_subagent", None)
    if fn is None:
        return "Error: Task sub-agent execution is not wired (internal)."
    return await fn(
        agent_name=(agent or "").strip(),
        prompt=(prompt or "").strip(),
        max_steps_override=max_steps,
    )


TASK_TOOL = Tool(
    name="Task",
    description=(
        "Delegate focused work to a **named subagent** (researcher, analyst, writer, etc.). "
        "Pass the subagent key in `agent` and a self-contained `prompt` for that worker — "
        "not the full chat transcript. Subagents run in parallel when the model emits multiple Task calls."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Subagent key registered for this run (e.g. researcher, analyst).",
            },
            "prompt": {
                "type": "string",
                "description": "Single-task instruction for the subagent.",
            },
            "max_steps": {
                "type": "integer",
                "description": "Optional max ReAct steps for this sub-run.",
            },
        },
        "required": ["agent", "prompt"],
    },
    handler=_task_handler,
    categories=["delegate"],
)
