"""Tool execution mixin for the Koraku agent."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Callable

from koraku.core.config import settings
from koraku.tools.policy import tool_stdout_indicates_error
from koraku.tools.tool_def import Tool
from koraku.agent.events import _emit_worker_status
from koraku.agent.utils import update_working_memory

log = logging.getLogger(__name__)

_TOOL_RUN_SEMAPHORE = asyncio.Semaphore(max(1, int(settings.tool_concurrency_limit)))


def _resolve_tool_from_active(tool_name: str, active_tools: list[Any]) -> Tool | None:
    resolved = "WebFetch" if tool_name == "WebPage" else tool_name
    for t in active_tools:
        if t.name == resolved:
            return t
    return None


class ToolExecutionMixin:
    def _update_memory(self, memory: list[dict[str, Any]], tool_results: list[dict[str, Any]]) -> None:
        update_working_memory(memory, tool_results)

    async def _execute_tools_parallel(
        self,
        tool_uses: list[dict[str, Any]],
        emit: Callable[[dict[str, Any]], None],
        active_tools: list[Any],
    ) -> list[dict[str, Any]]:
        for tool_use in tool_uses:
            exec_event = {
                "type": "tool_execution",
                "data": {
                    "tool": tool_use["name"],
                    "input": tool_use["input"],
                    "id": tool_use["id"],
                    "mode": "parallel" if len(tool_uses) > 1 else "sequential",
                },
            }
            emit(exec_event)

        names = [str(tu.get("name") or "tool") for tu in tool_uses]
        primary_tool = names[0] if names else None
        hb_iv = max(3.0, float(settings.agent_worker_heartbeat_seconds))
        stop_hb = asyncio.Event()

        async def _tool_heartbeat() -> None:
            while not stop_hb.is_set():
                try:
                    await asyncio.wait_for(stop_hb.wait(), timeout=hb_iv)
                except asyncio.TimeoutError:
                    if len(names) == 1:
                        msg = f"Running {names[0]}…"
                    else:
                        msg = f"Running {len(names)} tools…"
                    _emit_worker_status(emit, msg, tool_name=primary_tool, phase="tools")

        hb_task = asyncio.create_task(_tool_heartbeat())
        try:
            if len(tool_uses) == 1:
                return [await self._execute_single_tool(tool_uses[0], active_tools)]

            async def run_one(tu: dict[str, Any]) -> dict[str, Any]:
                return await self._execute_single_tool(tu, active_tools)

            results = await asyncio.gather(*[run_one(tu) for tu in tool_uses], return_exceptions=True)
            processed: list[dict[str, Any]] = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed.append({
                        "type": "tool_result",
                        "tool_use_id": tool_uses[i]["id"],
                        "content": f"Error: {result}",
                        "is_error": True,
                    })
                else:
                    processed.append(result)
            return processed
        finally:
            stop_hb.set()
            hb_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb_task

    async def _execute_single_tool(
        self,
        tool_use: dict[str, Any],
        active_tools: list[Any],
        max_retries: int = 2,
    ) -> dict[str, Any]:
        tool_name = tool_use["name"]
        tool_input = tool_use["input"]
        tool_id = tool_use["id"]

        if isinstance(tool_input, dict) and "_partial_json" in tool_input:
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": (
                    f"Error: Tool '{tool_name}' arguments were truncated (incomplete JSON). "
                    "Retry with a shorter payload or split large writes into smaller chunks."
                ),
                "is_error": True,
            }

        tool = _resolve_tool_from_active(tool_name, active_tools)
        if tool is None:
            return {
                "type": "tool_result", "tool_use_id": tool_id,
                "content": f"Error: Tool '{tool_name}' not found.", "is_error": True,
            }

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                async with _TOOL_RUN_SEMAPHORE:
                    result_text = await tool.run(**tool_input)
                is_error = tool_stdout_indicates_error(result_text, tool_name=tool_name)
                if not is_error:
                    return {"type": "tool_result", "tool_use_id": tool_id, "content": result_text, "is_error": False}
                last_error = result_text
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        return {
            "type": "tool_result", "tool_use_id": tool_id,
            "content": f"{last_error} (failed after {max_retries + 1} attempts)", "is_error": True,
        }
