"""Agent tools to list/create/update/delete saved Koraku automations (same store as the Automations UI)."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from src.automations import async_ops, scheduler
from src.automations.present import enrich_automation_row
from src.automations.validation import validate_cron_expression, validate_timezone_iana
from src.workspace.paths import workspace_dir


def _normalize_toolkits(toolkits: Any) -> list[str]:
    if toolkits is None:
        return []
    if isinstance(toolkits, str):
        return [x.strip().upper() for x in toolkits.split(",") if x.strip()]
    if isinstance(toolkits, list):
        return [str(x).strip().upper() for x in toolkits if str(x).strip()]
    return []


async def _automations_list(**_kwargs: Any) -> str:
    ws = workspace_dir()
    await async_ops.init_db(ws)
    raw = await async_ops.list_automations(ws)
    rows = await asyncio.gather(*[enrich_automation_row(dict(r)) for r in raw])
    return json.dumps({"automations": list(rows), "count": len(rows)}, indent=2)


async def _automations_create(**kwargs: Any) -> str:
    title = str(kwargs.get("title") or "").strip()
    natural_language_spec = str(kwargs.get("natural_language_spec") or "").strip()
    if not title or not natural_language_spec:
        return "Error: title and natural_language_spec are required and must be non-empty."
    trigger_mode = str(kwargs.get("trigger_mode") or "").strip()
    timezone = kwargs.get("timezone")
    cron_expression = kwargs.get("cron_expression")
    event_display = kwargs.get("event_display")
    headline = str(kwargs.get("headline") or "").strip()
    toolkits = kwargs.get("toolkits")
    status = str(kwargs.get("status") or "active").strip()
    ws = workspace_dir()
    await async_ops.init_db(ws)
    tm = trigger_mode.lower()
    if tm not in ("scheduled", "event"):
        return f"Error: trigger_mode must be 'scheduled' or 'event', got {trigger_mode!r}."
    st = status.lower()
    if st not in ("active", "paused"):
        return f"Error: status must be 'active' or 'paused', got {status!r}."
    try:
        if tm == "scheduled":
            tz_s = (str(timezone).strip() if timezone is not None else "")
            cr_s = (str(cron_expression).strip() if cron_expression is not None else "")
            if not tz_s or not cr_s:
                return (
                    "Error: scheduled automations require timezone (IANA, e.g. America/New_York) "
                    "and cron_expression (5 fields, e.g. '*/10 * * * *' every 10 minutes, '0 9 * * *' daily 9:00)."
                )
            validate_timezone_iana(tz_s)
            validate_cron_expression(cr_s)
        else:
            ev_s = (str(event_display).strip() if event_display is not None else "")
            if not ev_s:
                return (
                    "Error: event automations require event_display "
                    "(human-readable, e.g. 'Gmail: New email')."
                )
    except ValueError as e:
        return f"Error: {e}"

    tz_out = (str(timezone).strip() if timezone is not None else None) or None
    cr_out = (str(cron_expression).strip() if cron_expression is not None else None) or None
    ev_out = (str(event_display).strip() if event_display is not None else None) or None
    row = await async_ops.insert_automation(
        ws,
        title=title,
        headline=headline,
        natural_language_spec=natural_language_spec,
        trigger_mode=tm,  # type: ignore[arg-type]
        status=st,  # type: ignore[arg-type]
        timezone=tz_out,
        cron_expression=cr_out,
        event_display=ev_out,
        toolkits=_normalize_toolkits(toolkits),
    )
    await scheduler.sync_scheduler_jobs_async()
    enriched = await enrich_automation_row(row)
    return json.dumps({"ok": True, "automation": enriched}, indent=2)


async def _automations_update(**kwargs: Any) -> str:
    automation_id = kwargs.get("automation_id")
    title = kwargs.get("title")
    headline = kwargs.get("headline")
    natural_language_spec = kwargs.get("natural_language_spec")
    status = kwargs.get("status")
    timezone = kwargs.get("timezone")
    cron_expression = kwargs.get("cron_expression")
    event_display = kwargs.get("event_display")
    toolkits = kwargs.get("toolkits")
    ws = workspace_dir()
    await async_ops.init_db(ws)
    aid = str(automation_id or "").strip()
    if not aid:
        return "Error: automation_id is required."
    existing = await async_ops.get_automation(ws, aid)
    if not existing:
        return f"Error: no automation with id {aid!r}."
    def _opt_str(v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    st_kw = _opt_str(status)
    if st_kw is not None and st_kw not in ("active", "paused"):
        return f"Error: status must be 'active' or 'paused', got {status!r}."
    try:
        if cron_expression is not None:
            validate_cron_expression(str(cron_expression).strip())
        if timezone is not None:
            validate_timezone_iana(str(timezone).strip())
    except ValueError as e:
        return f"Error: {e}"

    tk = _normalize_toolkits(toolkits) if toolkits is not None else None
    row = await async_ops.update_automation(
        ws,
        aid,
        title=_opt_str(title),
        headline=_opt_str(headline),
        natural_language_spec=_opt_str(natural_language_spec),
        status=st_kw if st_kw is not None else None,  # type: ignore[arg-type]
        timezone=_opt_str(timezone),
        cron_expression=_opt_str(cron_expression),
        event_display=_opt_str(event_display),
        toolkits=tk,
    )
    if not row:
        return "Error: update failed."
    await scheduler.sync_scheduler_jobs_async()
    return json.dumps({"ok": True, "automation": await enrich_automation_row(row)}, indent=2)


async def _automations_delete(**kwargs: Any) -> str:
    automation_id = kwargs.get("automation_id")
    ws = workspace_dir()
    await async_ops.init_db(ws)
    aid = str(automation_id or "").strip()
    if not aid:
        return "Error: automation_id is required."
    if not await async_ops.delete_automation(ws, aid):
        return f"Error: no automation with id {aid!r}."
    await scheduler.sync_scheduler_jobs_async()
    return json.dumps({"ok": True, "deleted_id": aid}, indent=2)


# ---------------------------------------------------------------------------
# Tool wrappers (Tool class lives in tools.py)
# ---------------------------------------------------------------------------

def build_automation_tools():
    from src.tools.tool_def import Tool, ToolConfig

    return [
        Tool(
            config=ToolConfig(
                name="AutomationsList",
                description=(
                    "List all saved Koraku automations (id, title, trigger_mode, cron/timezone or event label, "
                    "status, toolkits). Use first to find automation_id before update/delete."
                ),
                input_schema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                categories=["automations"],
            ),
            handler=_automations_list,
        ),
        Tool(
            config=ToolConfig(
                name="AutomationsCreate",
                description=(
                    "Create a saved automation shown in the Automations app. "
                    "trigger_mode 'scheduled' needs timezone (IANA) and cron_expression (5 cron fields). "
                    "trigger_mode 'event' needs event_display (e.g. 'Gmail: New email'). "
                    "natural_language_spec is the full user intent (what to do when the automation runs)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short title for the list UI"},
                        "natural_language_spec": {
                            "type": "string",
                            "description": "Full instructions for what the automation should do when it runs",
                        },
                        "trigger_mode": {
                            "type": "string",
                            "description": "Either 'scheduled' or 'event'",
                        },
                        "timezone": {
                            "type": "string",
                            "description": "IANA timezone; required when trigger_mode is scheduled",
                        },
                        "cron_expression": {
                            "type": "string",
                            "description": "5-field cron; required when trigger_mode is scheduled (e.g. */10 * * * *)",
                        },
                        "event_display": {
                            "type": "string",
                            "description": "Human trigger label; required when trigger_mode is event",
                        },
                        "headline": {
                            "type": "string",
                            "description": "Optional subtitle, e.g. Gmail → Notion",
                        },
                        "toolkits": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional toolkit slugs for UI icons (GMAIL, NOTION, …)",
                        },
                        "status": {
                            "type": "string",
                            "description": "active or paused (default active)",
                        },
                    },
                    "required": ["title", "natural_language_spec", "trigger_mode"],
                },
                categories=["automations"],
            ),
            handler=_automations_create,
        ),
        Tool(
            config=ToolConfig(
                name="AutomationsUpdate",
                description=(
                    "Update an existing automation by automation_id. "
                    "Omit fields you do not want to change. Use status 'paused' or 'active' to pause/resume."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "automation_id": {"type": "string", "description": "UUID from AutomationsList"},
                        "title": {"type": "string"},
                        "headline": {"type": "string"},
                        "natural_language_spec": {"type": "string"},
                        "status": {"type": "string", "description": "active or paused"},
                        "timezone": {"type": "string"},
                        "cron_expression": {"type": "string"},
                        "event_display": {"type": "string"},
                        "toolkits": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["automation_id"],
                },
                categories=["automations"],
            ),
            handler=_automations_update,
        ),
        Tool(
            config=ToolConfig(
                name="AutomationsDelete",
                description="Delete an automation and its run history by automation_id.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "automation_id": {"type": "string", "description": "UUID from AutomationsList"},
                    },
                    "required": ["automation_id"],
                },
                categories=["automations"],
            ),
            handler=_automations_delete,
        ),
    ]
