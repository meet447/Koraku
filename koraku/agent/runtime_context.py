"""Execution context for a single agent run (workspace + tool policy)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from koraku.workspace.paths import workspace_dir

if TYPE_CHECKING:
    from koraku.tools.tool_def import Tool

# Chat API exposes only ``cloud`` and ``local``. ``server`` is internal: full tools on this
# process (automations, scheduler) and is never sent from ``POST /stream``.
ExecutionTarget = Literal["cloud", "local", "server"]

ChatExecutionMode = Literal["cloud", "local"]


def resolve_agent_workspace(
    workspace: str | None,
    run_context: AgentRunContext | None,
) -> str:
    """Effective workspace directory for this turn (explicit arg wins, then context, then cwd)."""
    if workspace is not None:
        return os.path.abspath(workspace)
    if run_context is not None and run_context.workspace_root:
        return os.path.abspath(run_context.workspace_root)
    return workspace_dir()


def resolve_execution_target(run_context: AgentRunContext | None) -> ExecutionTarget:
    if run_context is None:
        return "server"
    t = run_context.execution_target
    if t in ("cloud", "local", "server"):
        return t
    return "server"


@dataclass(frozen=True)
class AgentRunContext:
    """Binds one turn to a workspace root and tool policy.

    ``workspace_root``: when set, overrides the ``workspace`` argument to ``Agent.run`` if that
    argument is omitted. Process default remains ``workspace_dir()`` when both are unset.

    ``execution_target``:
    - ``cloud`` — restricted tools on the API host, **or** (when Blaxel is enabled + configured)
      file/shell tools run inside a per-session Blaxel sandbox VM.
    - ``local`` — full tools on a **linked desktop** (chat must not run this in-process here;
      use device transport when implemented).
    - ``server`` — full tools on this process (internal: automations, non-chat callers).
    """

    workspace_root: str | None = None
    execution_target: ExecutionTarget = "server"
    extra_tools: tuple[Tool, ...] = field(default_factory=tuple)
