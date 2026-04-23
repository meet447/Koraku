"""Shared presentation helpers for automation rows (HTTP API + agent tools)."""
from __future__ import annotations

from typing import Any

from src.automations import async_ops


def automation_status_line(row: dict[str, Any]) -> str:
    if row.get("status") == "paused":
        return "Paused"
    if row.get("trigger_mode") == "event":
        return "Waiting for event"
    if row.get("trigger_mode") == "scheduled":
        return "Scheduled"
    return ""


async def enrich_automation_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["status_line"] = automation_status_line(row)
    if row.get("trigger_mode") == "scheduled" and row.get("cron_expression") and row.get("timezone"):
        nxt = await async_ops.compute_next_cron_fire(
            str(row["cron_expression"]), str(row["timezone"])
        )
        if nxt:
            out["next_run_at_computed"] = nxt.isoformat()
    return out
