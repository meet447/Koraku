"""Execute a saved automation via the Koraku agent (local SDK)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Any, Callable

from koraku.agent.runtime_context import AgentRunContext
from koraku.automations.local_store import get_automation
from koraku.core.config import settings
from koraku.core.models import SessionState
from koraku.workspace.paths import workspace_dir

if TYPE_CHECKING:
    from koraku.agent.run import Agent

log = logging.getLogger(__name__)
_run_guard: dict[str, asyncio.Lock] = {}


def _lock_for(automation_id: str) -> asyncio.Lock:
    lock = _run_guard.get(automation_id)
    if lock is None:
        lock = asyncio.Lock()
        _run_guard[automation_id] = lock
    return lock


def build_automation_user_message(
    *,
    title: str,
    natural_language_spec: str,
    trigger_summary: str,
    toolkits: list[str] | None = None,
) -> str:
    tk = [str(x).strip().upper() for x in (toolkits or []) if str(x).strip()]
    toolkit_line = ""
    if tk:
        toolkit_line = (
            f"\n**Preferred integrations:** When you need external apps, call **ComposioRun** "
            f"with these toolkit slugs where relevant: {', '.join(tk)}.\n"
        )
    return (
        f"## Automation run\n"
        f"**Title:** {title}\n"
        f"**Trigger:** {trigger_summary}\n"
        f"{toolkit_line}\n"
        f"## Instructions\n{natural_language_spec.strip()}\n"
    )


async def run_automation(
    automation_id: str,
    *,
    agent: Agent | None,
    trigger_summary: str = "Manual run.",
    workspace: str | None = None,
) -> dict[str, Any]:
    """Run one automation through the agent loop."""
    ws = workspace or workspace_dir()
    auto = get_automation(automation_id, workspace=ws)
    if not auto:
        return {"ok": False, "error": "not_found", "automation_id": automation_id}
    if agent is None:
        return {"ok": False, "error": "llm_not_configured", "automation_id": automation_id}

    async with _lock_for(automation_id):
        session = SessionState(session_id=f"automation:{automation_id}:{uuid.uuid4().hex[:8]}")
        user_msg = build_automation_user_message(
            title=str(auto.get("title") or "Automation"),
            natural_language_spec=str(auto.get("natural_language_spec") or ""),
            trigger_summary=trigger_summary,
            toolkits=auto.get("toolkits") if isinstance(auto.get("toolkits"), list) else None,
        )
        last_error: str | None = None

        def _emit(_ev: dict[str, Any]) -> None:
            pass

        async def _consume() -> None:
            nonlocal last_error
            async for ev in agent.run(
                user_msg,
                session,
                _emit,
                workspace=ws,
                client_timezone=auto.get("timezone"),
                max_steps_override=settings.automation_max_steps,
                run_context=AgentRunContext(workspace_root=ws),
            ):
                if ev.get("type") == "agent.error":
                    d = ev.get("data") or {}
                    last_error = str(d.get("error") or ev)

        try:
            await asyncio.wait_for(
                _consume(),
                timeout=float(settings.automation_run_timeout_seconds),
            )
        except asyncio.TimeoutError:
            last_error = (
                f"Automation run exceeded {float(settings.automation_run_timeout_seconds):.0f}s time limit."
            )
        except Exception as e:
            last_error = str(e)

        if last_error:
            log.warning("automation %s failed: %s", automation_id, last_error)
            return {"ok": False, "error": last_error, "automation_id": automation_id}
        return {"ok": True, "automation_id": automation_id, "session_id": session.session_id}


async def queue_automation_run(
    automation_id: str,
    *,
    agent: Agent | None = None,
    trigger_summary: str = "Scheduled run.",
    workspace: str | None = None,
) -> dict[str, Any]:
    return await run_automation(
        automation_id,
        agent=agent,
        trigger_summary=trigger_summary,
        workspace=workspace,
    )
