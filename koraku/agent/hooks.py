"""Embedder-facing hooks around tool execution."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCallContext:
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str
    run_id: str | None = None
    session_id: str | None = None


@dataclass(frozen=True)
class HookResult:
    allow: bool = True
    message: str = ""
    updated_input: dict[str, Any] | None = None


PreToolUseHook = Callable[[ToolCallContext], Awaitable[HookResult | None]]
PostToolUseHook = Callable[[ToolCallContext, str, bool], Awaitable[None]]


@dataclass
class AgentHooks:
    pre_tool_use: PreToolUseHook | None = None
    post_tool_use: PostToolUseHook | None = None
    extra: dict[str, Any] = field(default_factory=dict)
