"""Non-blocking wrappers around ``automations_store`` (SQLite) for async call sites."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Literal

from src.automations.store import AutomationStatus, TriggerMode
from src.automations import store


async def init_db(workspace: str) -> None:
    await asyncio.to_thread(store.init_db, workspace)


async def list_automations(workspace: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(store.list_automations, workspace)


async def get_automation(workspace: str, automation_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(store.get_automation, workspace, automation_id)


async def insert_automation(
    workspace: str,
    *,
    title: str,
    headline: str,
    natural_language_spec: str,
    trigger_mode: TriggerMode,
    status: AutomationStatus,
    timezone: str | None,
    cron_expression: str | None,
    event_display: str | None,
    toolkits: list[str],
) -> dict[str, Any]:
    def _go() -> dict[str, Any]:
        return store.insert_automation(
            workspace,
            title=title,
            headline=headline,
            natural_language_spec=natural_language_spec,
            trigger_mode=trigger_mode,
            status=status,
            timezone=timezone,
            cron_expression=cron_expression,
            event_display=event_display,
            toolkits=toolkits,
        )

    return await asyncio.to_thread(_go)


async def update_automation(
    workspace: str,
    automation_id: str,
    *,
    title: str | None = None,
    headline: str | None = None,
    natural_language_spec: str | None = None,
    status: AutomationStatus | None = None,
    timezone: str | None = None,
    cron_expression: str | None = None,
    event_display: str | None = None,
    toolkits: list[str] | None = None,
) -> dict[str, Any] | None:
    def _go() -> dict[str, Any] | None:
        return store.update_automation(
            workspace,
            automation_id,
            title=title,
            headline=headline,
            natural_language_spec=natural_language_spec,
            status=status,
            timezone=timezone,
            cron_expression=cron_expression,
            event_display=event_display,
            toolkits=toolkits,
        )

    return await asyncio.to_thread(_go)


async def delete_automation(workspace: str, automation_id: str) -> bool:
    return await asyncio.to_thread(store.delete_automation, workspace, automation_id)


async def list_runs(workspace: str, automation_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return await asyncio.to_thread(store.list_runs, workspace, automation_id, limit)


async def insert_run_start(workspace: str, automation_id: str, *, trigger_summary: str) -> str:
    return await asyncio.to_thread(store.insert_run_start, workspace, automation_id, trigger_summary=trigger_summary)


async def finish_run(
    workspace: str,
    run_id: str,
    *,
    status: Literal["success", "failed"],
    result_summary: str | None,
    error: str | None,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    await asyncio.to_thread(
        store.finish_run,
        workspace,
        run_id,
        status=status,
        result_summary=result_summary,
        error=error,
        started_at=started_at,
        finished_at=finished_at,
    )


async def set_automation_run_times(
    workspace: str,
    automation_id: str,
    *,
    last_run_at: datetime | None = None,
    next_run_at: datetime | None = None,
) -> None:
    await asyncio.to_thread(
        store.set_automation_run_times,
        workspace,
        automation_id,
        last_run_at=last_run_at,
        next_run_at=next_run_at,
    )


async def compute_next_cron_fire(
    cron_expression: str, tz_name: str, base: datetime | None = None
) -> datetime | None:
    return await asyncio.to_thread(store.compute_next_cron_fire, cron_expression, tz_name, base)
