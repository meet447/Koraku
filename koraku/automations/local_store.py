"""Local filesystem automation store (``.koraku/automations/*.json``)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from koraku.workspace.paths import workspace_dir

TriggerMode = Literal["scheduled", "event"]
Status = Literal["active", "paused"]


def automations_dir(workspace: str | None = None) -> Path:
    root = Path(workspace or workspace_dir()).resolve()
    return root / ".koraku" / "automations"


def _path_for_id(automation_id: str, workspace: str | None = None) -> Path:
    aid = (automation_id or "").strip()
    if not aid or "/" in aid or "\\" in aid or ".." in aid:
        raise ValueError("invalid automation_id")
    return automations_dir(workspace) / f"{aid}.json"


def local_automations_available(workspace: str | None = None) -> bool:
    return True


def list_automations(*, workspace: str | None = None) -> list[dict[str, Any]]:
    root = automations_dir(workspace)
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(row, dict) and row.get("id"):
            rows.append(row)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return rows


def get_automation(automation_id: str, *, workspace: str | None = None) -> dict[str, Any] | None:
    path = _path_for_id(automation_id, workspace)
    if not path.is_file():
        return None
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return row if isinstance(row, dict) else None


def list_scheduled_active(*, workspace: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in list_automations(workspace=workspace):
        if row.get("trigger_mode") == "scheduled" and row.get("status") == "active":
            out.append(row)
    return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_automation(
    *,
    title: str,
    natural_language_spec: str,
    trigger_mode: TriggerMode,
    status: Status,
    timezone: str | None,
    cron_expression: str | None,
    headline: str = "",
    toolkits: list[str] | None = None,
    event_key: str | None = None,
    event_secret: str | None = None,
    workspace: str | None = None,
) -> dict[str, Any]:
    root = automations_dir(workspace)
    root.mkdir(parents=True, exist_ok=True)
    aid = str(uuid.uuid4())
    now = _now_iso()
    row: dict[str, Any] = {
        "id": aid,
        "title": title.strip(),
        "headline": headline.strip(),
        "natural_language_spec": natural_language_spec.strip(),
        "trigger_mode": trigger_mode,
        "status": status,
        "timezone": timezone,
        "cron_expression": cron_expression,
        "event_key": (event_key or "").strip() or None,
        "event_secret": (event_secret or "").strip() or None,
        "toolkits": list(toolkits or []),
        "created_at": now,
        "updated_at": now,
    }
    _path_for_id(aid, workspace).write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def update_automation(
    automation_id: str,
    *,
    title: str | None = None,
    headline: str | None = None,
    natural_language_spec: str | None = None,
    status: Status | None = None,
    timezone: str | None = None,
    cron_expression: str | None = None,
    event_key: str | None = None,
    event_secret: str | None = None,
    toolkits: list[str] | None = None,
    workspace: str | None = None,
) -> dict[str, Any] | None:
    row = get_automation(automation_id, workspace=workspace)
    if not row:
        return None
    if title is not None:
        row["title"] = title.strip()
    if headline is not None:
        row["headline"] = headline.strip()
    if natural_language_spec is not None:
        row["natural_language_spec"] = natural_language_spec.strip()
    if status is not None:
        row["status"] = status
    if timezone is not None:
        row["timezone"] = timezone
    if cron_expression is not None:
        row["cron_expression"] = cron_expression
    if event_key is not None:
        row["event_key"] = event_key.strip() or None
    if event_secret is not None:
        row["event_secret"] = event_secret.strip() or None
    if toolkits is not None:
        row["toolkits"] = list(toolkits)
    row["updated_at"] = _now_iso()
    _path_for_id(automation_id, workspace).write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def delete_automation(automation_id: str, *, workspace: str | None = None) -> bool:
    path = _path_for_id(automation_id, workspace)
    if not path.is_file():
        return False
    path.unlink()
    return True
