"""Tool execution mixin for the Koraku agent."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Callable

from koraku.core.config import settings
from koraku.tools.policy import tool_stdout_indicates_error
from koraku.tools.tool_def import Tool
from koraku.agent.active_run import (
    get_active_emit,
    get_active_hooks,
    get_active_permission_mode,
    get_active_run_id,
    get_active_session_id,
    get_active_ask_user_timeout,
)
from koraku.agent.events import _emit_worker_status
from koraku.agent.hooks import HookResult, ToolCallContext
from koraku.agent.permissions import (
    CONFIRM_DENIED_MESSAGE,
    requires_user_approval,
    tool_blocked_message,
)
from koraku.agent.pending_interactions import register, wait_for_response
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

    async def _maybe_request_tool_approval(
        self,
        ctx: ToolCallContext,
        emit: Callable[[dict[str, Any]], None],
    ) -> HookResult | None:
        mode = get_active_permission_mode()
        if not requires_user_approval(ctx.tool_name, mode):
            return None
        run_id = get_active_run_id()
        interaction_id, future = await register(
            "approval",
            run_id=run_id,
            payload={
                "tool": ctx.tool_name,
                "input": ctx.tool_input,
                "tool_use_id": ctx.tool_use_id,
            },
        )
        emit({
            "type": "agent.approval",
            "data": {
                "interaction_id": interaction_id,
                "approval_id": interaction_id,
                "run_id": run_id or "",
                "tool": ctx.tool_name,
                "input": ctx.tool_input,
                "tool_use_id": ctx.tool_use_id,
            },
        })
        try:
            response = await wait_for_response(
                interaction_id,
                future,
                timeout_seconds=get_active_ask_user_timeout(),
            )
        except asyncio.TimeoutError:
            return HookResult(allow=False, message="Error: approval timed out waiting for the user.")
        approved = bool(response.get("approved"))
        if not approved:
            return HookResult(allow=False, message=CONFIRM_DENIED_MESSAGE)
        updated = response.get("updated_input")
        if isinstance(updated, dict):
            return HookResult(allow=True, updated_input=updated)
        return HookResult(allow=True)

    async def _apply_pre_tool_hooks(
        self,
        ctx: ToolCallContext,
        emit: Callable[[dict[str, Any]], None],
    ) -> HookResult:
        blocked = tool_blocked_message(ctx.tool_name, get_active_permission_mode())
        if blocked:
            return HookResult(allow=False, message=blocked)

        approval = await self._maybe_request_tool_approval(ctx, emit)
        if approval is not None and not approval.allow:
            return approval
        if approval is not None and approval.updated_input is not None:
            ctx = ToolCallContext(
                tool_name=ctx.tool_name,
                tool_input=approval.updated_input,
                tool_use_id=ctx.tool_use_id,
                run_id=ctx.run_id,
                session_id=ctx.session_id,
            )

        hooks = get_active_hooks()
        if hooks is not None and hooks.pre_tool_use is not None:
            custom = await hooks.pre_tool_use(ctx)
            if custom is not None and not custom.allow:
                return custom
            if custom is not None and custom.updated_input is not None:
                return HookResult(allow=True, updated_input=custom.updated_input)

        if approval is not None and approval.updated_input is not None:
            return HookResult(allow=True, updated_input=approval.updated_input)
        return HookResult(allow=True)

    async def _execute_single_tool(
        self,
        tool_use: dict[str, Any],
        active_tools: list[Any],
        max_retries: int = 2,
    ) -> dict[str, Any]:
        tool_name = tool_use["name"]
        tool_input = tool_use["input"]
        tool_id = tool_use["id"]
        emit = get_active_emit()

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

        ctx = ToolCallContext(
            tool_name=tool_name,
            tool_input=dict(tool_input) if isinstance(tool_input, dict) else {},
            tool_use_id=tool_id,
            run_id=get_active_run_id(),
            session_id=get_active_session_id(),
        )
        if emit is not None:
            pre = await self._apply_pre_tool_hooks(ctx, emit)
            if not pre.allow:
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": pre.message or f"Error: Tool '{tool_name}' was blocked.",
                    "is_error": True,
                }
            if pre.updated_input is not None:
                tool_input = pre.updated_input
                tool_use = {**tool_use, "input": tool_input}

        last_error = ""
        result_text = ""
        is_error = True
        for attempt in range(max_retries + 1):
            try:
                async with _TOOL_RUN_SEMAPHORE:
                    result_text = await tool.run(**tool_input)
                is_error = tool_stdout_indicates_error(result_text, tool_name=tool_name)
                if not is_error:
                    break
                last_error = result_text
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                last_error = str(e)
                result_text = last_error
                is_error = True
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        hooks = get_active_hooks()
        if hooks is not None and hooks.post_tool_use is not None:
            post_ctx = ToolCallContext(
                tool_name=tool_name,
                tool_input=dict(tool_input) if isinstance(tool_input, dict) else {},
                tool_use_id=tool_id,
                run_id=get_active_run_id(),
                session_id=get_active_session_id(),
            )
        with contextlib.suppress(Exception):
            await hooks.post_tool_use(post_ctx, result_text, is_error)

        from koraku.agent.run_artifacts import log_tool_result

        log_tool_result(
            tool_name=tool_name,
            tool_use_id=tool_id,
            tool_input=dict(tool_input) if isinstance(tool_input, dict) else {},
            result=result_text,
            is_error=is_error,
        )

        if not is_error:
            return {"type": "tool_result", "tool_use_id": tool_id, "content": result_text, "is_error": False}

        if last_error and "failed after" not in last_error:
            content = f"{last_error} (failed after {max_retries + 1} attempts)"
        else:
            content = last_error or result_text
        return {
            "type": "tool_result", "tool_use_id": tool_id,
            "content": content, "is_error": True,
        }
