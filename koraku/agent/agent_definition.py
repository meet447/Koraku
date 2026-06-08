"""Named subagent definitions for the Task delegation tool."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    """Configuration for a scoped subagent invoked via **Task**.

    ``tools`` lists allowed tool names (e.g. ``Read``, ``WebSearch``). When empty,
    the subagent inherits the parent's non-delegation tools minus **Task**.
    """

    description: str
    prompt: str
    tools: tuple[str, ...] = ()
    model: str | None = None
    provider: str | None = None
    max_steps: int | None = None
