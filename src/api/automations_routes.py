"""FastAPI routes for saved automations (CRUD, runs, manual run)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from src.automations import async_ops, runner as automation_runner, scheduler as automation_scheduler
from src.automations.present import enrich_automation_row
from src.automations.validation import validate_cron_expression, validate_timezone_iana
from src.workspace.paths import workspace_dir

router = APIRouter(prefix="/api/automations", tags=["automations"])


class AutomationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    headline: str = Field(default="", max_length=200)
    natural_language_spec: str = Field(..., min_length=1, max_length=50_000)
    trigger_mode: str = Field(..., pattern="^(scheduled|event)$")
    status: str = Field(default="active", pattern="^(active|paused)$")
    timezone: str | None = None
    cron_expression: str | None = None
    event_display: str | None = Field(default=None, max_length=200)
    toolkits: list[str] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def check_trigger_fields(self) -> "AutomationCreate":
        if self.trigger_mode == "scheduled":
            if not (self.timezone or "").strip() or not (self.cron_expression or "").strip():
                raise ValueError("scheduled automations require timezone and cron_expression")
            validate_timezone_iana(self.timezone or "")
            validate_cron_expression(self.cron_expression or "")
        else:
            if not (self.event_display or "").strip():
                raise ValueError("event automations require event_display (e.g. 'Gmail: New email')")
        return self


class AutomationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    headline: str | None = Field(default=None, max_length=200)
    natural_language_spec: str | None = Field(default=None, min_length=1, max_length=50_000)
    status: str | None = Field(default=None, pattern="^(active|paused)$")
    timezone: str | None = None
    cron_expression: str | None = None
    event_display: str | None = Field(default=None, max_length=200)
    toolkits: list[str] | None = Field(default=None, max_length=24)

    @model_validator(mode="after")
    def check_cron(self) -> "AutomationPatch":
        if self.cron_expression is not None:
            validate_cron_expression(self.cron_expression)
        if self.timezone is not None:
            validate_timezone_iana(self.timezone)
        return self


@router.get("")
async def automations_list():
    ws = workspace_dir()
    await async_ops.init_db(ws)
    rows = await async_ops.list_automations(ws)
    items = await asyncio.gather(*[enrich_automation_row(r) for r in rows])
    return {"items": list(items)}


@router.post("")
async def automations_create(body: AutomationCreate):
    ws = workspace_dir()
    await async_ops.init_db(ws)
    row = await async_ops.insert_automation(
        ws,
        title=body.title,
        headline=body.headline,
        natural_language_spec=body.natural_language_spec,
        trigger_mode=body.trigger_mode,  # type: ignore[arg-type]
        status=body.status,  # type: ignore[arg-type]
        timezone=body.timezone,
        cron_expression=body.cron_expression,
        event_display=body.event_display,
        toolkits=body.toolkits,
    )
    await automation_scheduler.sync_scheduler_jobs_async()
    return await enrich_automation_row(row)


@router.get("/{automation_id}")
async def automations_get(automation_id: str):
    ws = workspace_dir()
    row = await async_ops.get_automation(ws, automation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Automation not found")
    return await enrich_automation_row(row)


@router.patch("/{automation_id}")
async def automations_patch(automation_id: str, body: AutomationPatch):
    ws = workspace_dir()
    existing = await async_ops.get_automation(ws, automation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Automation not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return await enrich_automation_row(existing)
    row = await async_ops.update_automation(
        ws,
        automation_id,
        title=patch.get("title"),
        headline=patch.get("headline"),
        natural_language_spec=patch.get("natural_language_spec"),
        status=patch.get("status"),  # type: ignore[arg-type]
        timezone=patch.get("timezone"),
        cron_expression=patch.get("cron_expression"),
        event_display=patch.get("event_display"),
        toolkits=patch.get("toolkits"),
    )
    await automation_scheduler.sync_scheduler_jobs_async()
    assert row is not None
    return await enrich_automation_row(row)


@router.delete("/{automation_id}")
async def automations_delete(automation_id: str):
    ws = workspace_dir()
    if not await async_ops.delete_automation(ws, automation_id):
        raise HTTPException(status_code=404, detail="Automation not found")
    await automation_scheduler.sync_scheduler_jobs_async()
    return {"ok": True}


@router.get("/{automation_id}/runs")
async def automations_runs(automation_id: str, limit: int = 50):
    ws = workspace_dir()
    if not await async_ops.get_automation(ws, automation_id):
        raise HTTPException(status_code=404, detail="Automation not found")
    return {"items": await async_ops.list_runs(ws, automation_id, limit=limit)}


@router.post("/{automation_id}/run")
async def automations_run_now(automation_id: str, request: Request):
    ws = workspace_dir()
    if not await async_ops.get_automation(ws, automation_id):
        raise HTTPException(status_code=404, detail="Automation not found")
    agent = getattr(request.app.state, "koraku_agent", None)
    try:
        return await automation_runner.execute_automation(
            ws,
            automation_id,
            agent=agent,
            trigger_summary="Manual run from the Automations page.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Automation run crashed: {e!s}") from e
