"""SSE and tracing event emitters for the Koraku agent."""
from __future__ import annotations

from typing import Any, Callable


def _emit_worker_status(
    emit: Callable[[dict[str, Any]], None],
    message: str,
    *,
    tool_name: str | None = None,
    phase: str | None = None,
) -> None:
    data: dict[str, Any] = {"trace": "worker_status", "message": message}
    if tool_name:
        data["tool"] = tool_name
    if phase:
        data["phase"] = phase
    emit({"type": "agent.trace", "data": data})
