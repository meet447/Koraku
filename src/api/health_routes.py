"""Process health and configuration snapshot."""
from __future__ import annotations

from fastapi import APIRouter, Request

from src.automations import scheduler as automation_scheduler
from src.integrations import composio as composio_runtime
from src.agent.sessions import sessions
from src.core.config import settings
from src.llm.catalog import any_llm_configured, configured_provider_ids, default_chat_model

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    mode = getattr(request.app.state, "server_mode", "unconfigured")
    return {
        "status": "ok",
        "agent": settings.agent_name,
        "version": settings.version,
        "mode": mode,
        "composio_configured": composio_runtime.is_configured(),
        "llm_configured": any_llm_configured(),
        "llm_provider": settings.llm_provider,
        "configured_providers": configured_provider_ids(),
        "default_model": default_chat_model(),
        "max_steps_standard": settings.max_steps,
        "max_steps_extended": settings.research_max_steps,
        "exa_enabled": bool(settings.exa_api_key),
        "firecrawl_enabled": bool(settings.firecrawl_api_key),
        "session_ttl_hours": settings.session_ttl_hours,
        "session_store_max": settings.session_store_max,
        "active_chat_sessions": len(sessions),
        "automation_scheduler_running": automation_scheduler.is_running(),
        "automation_scheduler_leader": automation_scheduler.is_automation_scheduler_leader(),
        "automation_scheduler_enabled": settings.automation_scheduler_enabled,
        "automation_max_steps": settings.automation_max_steps,
        "automation_run_timeout_seconds": settings.automation_run_timeout_seconds,
    }
