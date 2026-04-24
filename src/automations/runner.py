"""Execute a saved automation via the Koraku agent (scheduled, manual, or future event runs)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Callable

from src.automations import async_ops
from src.core.config import settings
from src.core.models import SessionState, utcnow

from src.agent.run import RunContext

if TYPE_CHECKING:
    from src.agent.run import Agent

log = logging.getLogger(__name__)

# Avoid overlapping runs for the same automation (scheduler + manual).
_run_guard: dict[str, asyncio.Lock] = {}


def _lock_for(automation_id: str) -> asyncio.Lock:
    lock = _run_guard.get(automation_id)
    if lock is None:
        lock = asyncio.Lock()
        _run_guard[automation_id] = lock
    return lock


def _blocks_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            t = block.get("text")
            if isinstance(t, str) and t.strip():
                parts.append(t.strip())
    return "\n\n".join(parts).strip()


def _last_assistant_summary(session: SessionState, max_chars: int = 2000) -> str:
    for msg in reversed(session.messages):
        if getattr(msg, "role", None) == "assistant":
            text = _blocks_to_text(msg.content)
            if text:
                return text[:max_chars]
    return ""


def build_automation_user_message(
    *,
    title: str,
    natural_language_spec: str,
    trigger_summary: str,
) -> str:
    return (
        "You are executing a saved Koraku automation (automated run).\n\n"
        f"**Automation title:** {title}\n\n"
        f"**What the user wants:**\n{natural_language_spec.strip()}\n\n"
        f"**Trigger context:**\n{trigger_summary.strip()}\n\n"
        "Follow the instructions completely. Prefer concrete actions (tools) when needed. "
        "End with a short summary of what you did."
    )


async def execute_automation(
    workspace: str,
    automation_id: str,
    *,
    agent: Agent | None,
    trigger_summary: str,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run one automation turn; persists a row in ``automation_runs``."""
    auto = await async_ops.get_automation(workspace, automation_id)
    if auto is None:
        return {"ok": False, "error": "automation_not_found"}

    lock = _lock_for(automation_id)

    async with lock:
        started = utcnow()
        run_id = await async_ops.insert_run_start(
            workspace, automation_id, trigger_summary=trigger_summary
        )

        if agent is None:
            await async_ops.finish_run(
                workspace,
                run_id,
                status="failed",
                result_summary=None,
                error="LLM is not configured on this server.",
                started_at=started,
                finished_at=utcnow(),
            )
            await async_ops.set_automation_run_times(
                workspace, automation_id, last_run_at=utcnow()
            )
            return {"ok": False, "error": "llm_not_configured", "run_id": run_id}

        session = SessionState(session_id=f"auto-{automation_id}-{run_id}")
        user_msg = build_automation_user_message(
            title=auto["title"],
            natural_language_spec=auto["natural_language_spec"],
            trigger_summary=trigger_summary,
        )

        def _emit(ev: dict[str, Any]) -> None:
            if emit is not None:
                emit(ev)

        last_error: str | None = None
        t0 = time.perf_counter()

        async def _consume_agent() -> None:
            nonlocal last_error
            context = RunContext(
                workspace=workspace,
                client_timezone=auto.get("timezone"),
                max_steps_override=settings.automation_max_steps,
            )
            async for ev in agent.run(
                user_msg,
                session,
                _emit,
                context=context,
            ):
                if ev.get("type") == "agent.error":
                    d = ev.get("data") or {}
                    last_error = str(d.get("error") or ev)

        try:
            await asyncio.wait_for(
                _consume_agent(),
                timeout=float(settings.automation_run_timeout_seconds),
            )
        except asyncio.TimeoutError:
            last_error = (
                f"Automation run exceeded {float(settings.automation_run_timeout_seconds):.0f}s time limit."
            )
        except Exception as e:
            last_error = str(e)

        finished = utcnow()
        summary = _last_assistant_summary(session)
        if summary:
            status = "success"
            err = None
            res = summary
        else:
            status = "failed"
            err = last_error or "No assistant output captured."
            res = None

        await async_ops.finish_run(
            workspace,
            run_id,
            status=status,  # type: ignore[arg-type]
            result_summary=res,
            error=err,
            started_at=started,
            finished_at=finished,
        )
        await async_ops.set_automation_run_times(
            workspace, automation_id, last_run_at=finished
        )

        try:
            from src.automations import scheduler

            await asyncio.to_thread(
                scheduler.refresh_next_run_metadata,
                workspace,
                automation_id,
            )
        except Exception:
            pass

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        log.info(
            "automation_run automation_id=%s run_id=%s status=%s duration_ms=%s",
            automation_id,
            run_id,
            status,
            elapsed_ms,
        )
        return {
            "ok": status == "success",
            "run_id": run_id,
            "status": status,
            "duration_ms": elapsed_ms,
            "error": err,
            "result_summary": res,
        }
