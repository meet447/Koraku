"""Dispatch event-triggered automations."""
from __future__ import annotations

import logging
from typing import Any

from koraku.automations.local_store import list_automations
from koraku.automations.runner import queue_automation_run
from koraku.core.secret_compare import secrets_equal
from koraku.workspace.paths import workspace_dir

log = logging.getLogger(__name__)


def list_event_active(*, workspace: str | None = None) -> list[dict[str, Any]]:
    return [
        row
        for row in list_automations(workspace=workspace)
        if row.get("trigger_mode") == "event" and row.get("status") == "active"
    ]


def find_automations_for_event(event_key: str, *, workspace: str | None = None) -> list[dict[str, Any]]:
    key = (event_key or "").strip().lower()
    if not key:
        return []
    out: list[dict[str, Any]] = []
    for row in list_event_active(workspace=workspace):
        row_key = str(row.get("event_key") or "").strip().lower()
        if row_key == key:
            out.append(row)
    return out


async def trigger_event(
    event_key: str,
    *,
    payload: dict[str, Any] | None = None,
    agent: Any = None,
    workspace: str | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    ws = workspace or workspace_dir()
    matches = find_automations_for_event(event_key, workspace=ws)
    if not matches:
        return {"ok": False, "error": "no_matching_automation", "event_key": event_key}

    results: list[dict[str, Any]] = []
    for row in matches:
        expected = str(row.get("event_secret") or "").strip()
        if expected and not secrets_equal(expected, str(secret or "").strip()):
            return {"ok": False, "error": "invalid_secret", "event_key": event_key}
        summary = f"Event `{event_key}`"
        if payload:
            summary += f" payload={payload!r}"
        result = await queue_automation_run(
            str(row["id"]),
            agent=agent,
            trigger_summary=summary,
            workspace=ws,
        )
        results.append(result)
    return {"ok": True, "event_key": event_key, "runs": results, "count": len(results)}
