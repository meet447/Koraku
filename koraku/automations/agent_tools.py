"""Agent tools to manage local Koraku automations (``.koraku/automations/``)."""

from __future__ import annotations

import json
from typing import Any

from koraku.automations import local_store, scheduler
from koraku.automations.validation import validate_cron_expression, validate_timezone_iana
from koraku.workspace.agent_workspace import get_active_agent_workspace
from koraku.workspace.paths import workspace_dir


def _workspace() -> str:
    return get_active_agent_workspace() or workspace_dir()


def _normalize_toolkits(toolkits: Any) -> list[str]:
    if toolkits is None:
        return []
    if isinstance(toolkits, str):
        return [x.strip().upper() for x in toolkits.split(",") if x.strip()]
    if isinstance(toolkits, list):
        return [str(x).strip().upper() for x in toolkits if str(x).strip()]
    return []


async def _automations_list(**_kwargs: Any) -> str:
    rows = local_store.list_automations(workspace=_workspace())
    return json.dumps({"automations": rows, "count": len(rows)}, indent=2)


async def _automations_create(**kwargs: Any) -> str:
    title = str(kwargs.get("title") or "").strip()
    natural_language_spec = str(kwargs.get("natural_language_spec") or "").strip()
    if not title or not natural_language_spec:
        return "Error: title and natural_language_spec are required and must be non-empty."
    trigger_mode = str(kwargs.get("trigger_mode") or "").strip().lower()
    if trigger_mode not in ("scheduled", "event"):
        return f"Error: trigger_mode must be 'scheduled' or 'event', got {trigger_mode!r}."
    status = str(kwargs.get("status") or "active").strip().lower()
    if status not in ("active", "paused"):
        return f"Error: status must be 'active' or 'paused', got {status!r}."
    timezone = kwargs.get("timezone")
    cron_expression = kwargs.get("cron_expression")
    event_key = str(kwargs.get("event_key") or "").strip()
    event_secret = str(kwargs.get("event_secret") or "").strip()
    tz_s = str(timezone).strip() if timezone is not None else ""
    cr_s = str(cron_expression).strip() if cron_expression is not None else ""
    if trigger_mode == "scheduled":
        if not tz_s or not cr_s:
            return (
                "Error: scheduled automations require timezone (IANA, e.g. America/New_York) "
                "and cron_expression (5 fields, e.g. '0 9 * * *')."
            )
        try:
            validate_timezone_iana(tz_s)
            validate_cron_expression(cr_s)
        except ValueError as e:
            return f"Error: {e}"
    else:
        if not event_key:
            return (
                "Error: event automations require event_key (slug used in "
                "POST /api/automations/trigger/{event_key})."
            )
        tz_s = tz_s or None
        cr_s = cr_s or None
    row = local_store.insert_automation(
        title=title,
        natural_language_spec=natural_language_spec,
        trigger_mode=trigger_mode,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        timezone=tz_s or None,
        cron_expression=cr_s or None,
        event_key=event_key or None,
        event_secret=event_secret or None,
        headline=str(kwargs.get("headline") or "").strip(),
        toolkits=_normalize_toolkits(kwargs.get("toolkits")),
        workspace=_workspace(),
    )
    await scheduler.sync_scheduler_jobs_async()
    return json.dumps({"ok": True, "automation": row}, indent=2)


async def _automations_update(**kwargs: Any) -> str:
    automation_id = str(kwargs.get("automation_id") or "").strip()
    if not automation_id:
        return "Error: automation_id is required."
    existing = local_store.get_automation(automation_id, workspace=_workspace())
    if not existing:
        return f"Error: no automation with id {automation_id!r}."

    def _opt_str(v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    st_kw = _opt_str(kwargs.get("status"))
    if st_kw is not None and st_kw not in ("active", "paused"):
        return f"Error: status must be 'active' or 'paused', got {kwargs.get('status')!r}."
    try:
        if kwargs.get("cron_expression") is not None:
            validate_cron_expression(str(kwargs.get("cron_expression")).strip())
        if kwargs.get("timezone") is not None:
            validate_timezone_iana(str(kwargs.get("timezone")).strip())
    except ValueError as e:
        return f"Error: {e}"

    tk = _normalize_toolkits(kwargs.get("toolkits")) if kwargs.get("toolkits") is not None else None
    row = local_store.update_automation(
        automation_id,
        title=_opt_str(kwargs.get("title")),
        headline=_opt_str(kwargs.get("headline")),
        natural_language_spec=_opt_str(kwargs.get("natural_language_spec")),
        status=st_kw if st_kw is not None else None,  # type: ignore[arg-type]
        timezone=_opt_str(kwargs.get("timezone")),
        cron_expression=_opt_str(kwargs.get("cron_expression")),
        toolkits=tk,
        workspace=_workspace(),
    )
    if not row:
        return "Error: update failed."
    await scheduler.sync_scheduler_jobs_async()
    return json.dumps({"ok": True, "automation": row}, indent=2)


async def _automations_delete(**kwargs: Any) -> str:
    automation_id = str(kwargs.get("automation_id") or "").strip()
    if not automation_id:
        return "Error: automation_id is required."
    if not local_store.delete_automation(automation_id, workspace=_workspace()):
        return f"Error: no automation with id {automation_id!r}."
    await scheduler.sync_scheduler_jobs_async()
    return json.dumps({"ok": True, "deleted_id": automation_id}, indent=2)


def build_automation_tools() -> list[Any]:
    from koraku.tools.tool_def import Tool

    return [
        Tool(
            name="AutomationsList",
            description=(
                "List saved Koraku automations (id, title, trigger, cron/timezone, status, toolkits). "
                "Stored under .koraku/automations/ in the workspace."
            ),
            input_schema={"type": "object", "properties": {}, "required": []},
            handler=_automations_list,
            categories=["automations"],
        ),
        Tool(
            name="AutomationsCreate",
            description=(
                "Create an automation. Use trigger_mode 'scheduled' with timezone + cron_expression, "
                "or trigger_mode 'event' with event_key (webhook slug)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short title"},
                    "natural_language_spec": {
                        "type": "string",
                        "description": "Full instructions when the automation runs",
                    },
                    "trigger_mode": {
                        "type": "string",
                        "description": "'scheduled' or 'event'",
                    },
                    "timezone": {"type": "string", "description": "IANA timezone (scheduled)"},
                    "cron_expression": {"type": "string", "description": "5-field cron (scheduled)"},
                    "event_key": {
                        "type": "string",
                        "description": "Webhook slug for event trigger (POST /api/automations/trigger/{event_key})",
                    },
                    "event_secret": {
                        "type": "string",
                        "description": "Optional shared secret (X-Koraku-Event-Secret header)",
                    },
                    "headline": {"type": "string", "description": "Optional subtitle"},
                    "toolkits": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional Composio toolkit slugs",
                    },
                    "status": {"type": "string", "description": "active or paused"},
                },
                "required": ["title", "natural_language_spec", "trigger_mode"],
            },
            handler=_automations_create,
            categories=["automations"],
        ),
        Tool(
            name="AutomationsUpdate",
            description="Update an automation by automation_id. Omit fields you do not want to change.",
            input_schema={
                "type": "object",
                "properties": {
                    "automation_id": {"type": "string"},
                    "title": {"type": "string"},
                    "headline": {"type": "string"},
                    "natural_language_spec": {"type": "string"},
                    "status": {"type": "string"},
                    "timezone": {"type": "string"},
                    "cron_expression": {"type": "string"},
                    "event_key": {"type": "string"},
                    "event_secret": {"type": "string"},
                    "toolkits": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["automation_id"],
            },
            handler=_automations_update,
            categories=["automations"],
        ),
        Tool(
            name="AutomationsDelete",
            description="Delete an automation by automation_id.",
            input_schema={
                "type": "object",
                "properties": {"automation_id": {"type": "string"}},
                "required": ["automation_id"],
            },
            handler=_automations_delete,
            categories=["automations"],
        ),
    ]
