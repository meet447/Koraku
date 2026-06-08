"""Permission modes and tool allowlists for agent runs."""
from __future__ import annotations

from typing import Any, Literal

PermissionMode = Literal["default", "plan", "read_only", "confirm_sensitive"]

PLAN_MODE_TOOLS: frozenset[str] = frozenset({
    "AskUser",
    "Read",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "TodoWrite",
})

READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "AskUser",
    "Read",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
})

SENSITIVE_TOOLS: frozenset[str] = frozenset({
    "Bash",
    "Write",
    "Edit",
    "ComposioRun",
    "AutomationsCreate",
    "AutomationsUpdate",
    "AutomationsDelete",
})

READ_ONLY_BLOCKED_MESSAGE = (
    "Blocked: permission mode is read_only. Only read and search tools are allowed."
)
PLAN_BLOCKED_MESSAGE = (
    "Blocked: permission mode is plan. Ask clarifying questions with AskUser before "
    "using write, shell, or integration tools."
)
CONFIRM_DENIED_MESSAGE = "Blocked: user declined approval for this tool call."


def normalize_permission_mode(value: str | None) -> PermissionMode:
    raw = (value or "default").strip().lower()
    if raw in ("default", "plan", "read_only", "confirm_sensitive"):
        return raw  # type: ignore[return-value]
    return "default"


def filter_tools_for_permission_mode(tools: list[Any], mode: PermissionMode) -> list[Any]:
    if mode == "default" or mode == "confirm_sensitive":
        return list(tools)
    allowed = PLAN_MODE_TOOLS if mode == "plan" else READ_ONLY_TOOLS
    return [t for t in tools if getattr(t, "name", "") in allowed]


def tool_blocked_message(tool_name: str, mode: PermissionMode) -> str | None:
    if mode == "read_only" and tool_name not in READ_ONLY_TOOLS:
        return READ_ONLY_BLOCKED_MESSAGE
    if mode == "plan" and tool_name not in PLAN_MODE_TOOLS:
        return PLAN_BLOCKED_MESSAGE
    return None


def requires_user_approval(tool_name: str, mode: PermissionMode) -> bool:
    return mode == "confirm_sensitive" and tool_name in SENSITIVE_TOOLS
