"""Process health and configuration snapshot."""
from __future__ import annotations

from fastapi import APIRouter, Request

from koraku.automations import scheduler as automation_scheduler
from koraku.automations.supabase_store import supabase_automations_configured
from koraku.integrations.supabase_chat_history import supabase_chat_history_configured
from koraku.integrations import composio as composio_runtime
from koraku.integrations.blaxel_runtime import cloud_blaxel_block_reason
from koraku.core.session_store import active_session_count
from koraku.core.config import settings
from koraku.llm.catalog import any_llm_configured, configured_provider_ids, default_chat_model

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
        "session_store_backend": settings.session_store_backend,
        "auth_backend": settings.auth_backend,
        "allow_server_execution_in_chat": settings.allow_server_execution_in_chat,
        "allow_local_execution_in_chat": settings.allow_local_execution_in_chat,
        "agent_llm_stream_timeout_seconds": settings.agent_llm_stream_timeout_seconds,
        "agent_tool_phase_timeout_seconds": settings.agent_tool_phase_timeout_seconds,
        "active_chat_sessions": active_session_count(),
        "blaxel_cloud_sandbox_enabled": settings.blaxel_cloud_sandbox_enabled,
        "cloud_chat_sandbox_block_reason": cloud_blaxel_block_reason(settings),
        "automation_scheduler_running": automation_scheduler.is_running(),
        "automation_scheduler_leader": automation_scheduler.is_automation_scheduler_leader(),
        "automation_scheduler_enabled": settings.automation_scheduler_enabled,
        "automation_max_steps": settings.automation_max_steps,
        "automation_run_timeout_seconds": settings.automation_run_timeout_seconds,
        "automations_supabase_configured": supabase_automations_configured(),
        "chat_history_supabase_configured": supabase_chat_history_configured(),
    }
