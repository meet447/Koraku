"""Embeddable Koraku SDK settings (agent, LLM, tools, optional HTTP server)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _PACKAGE_DIR.parent


class SdkSettings(BaseSettings):
    """SDK / agent / self-host server configuration."""

    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    host: str = "127.0.0.1"
    port: int = 8000
    cors_allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS", "cors_allowed_origins"),
    )
    trusted_proxy_cidrs: str = Field(
        default="",
        validation_alias=AliasChoices("TRUSTED_PROXY_CIDRS", "trusted_proxy_cidrs"),
    )
    max_request_body_bytes: int = Field(
        default=16 * 1024 * 1024,
        validation_alias=AliasChoices("MAX_REQUEST_BODY_BYTES", "max_request_body_bytes"),
    )

    default_execution_target: str = Field(
        default="local",
        validation_alias=AliasChoices("DEFAULT_EXECUTION_TARGET", "default_execution_target"),
    )
    memory_backend: str = Field(
        default="filesystem",
        validation_alias=AliasChoices("MEMORY_BACKEND", "memory_backend"),
    )
    session_store_backend: str = Field(
        default="memory",
        validation_alias=AliasChoices(
            "SESSION_STORE_BACKEND",
            "KORAKU_SESSION_STORE",
            "session_store_backend",
        ),
    )

    sse_keepalive_seconds: float = 12.0
    session_ttl_hours: float = 168.0
    session_store_max: int = 2000
    agent_concurrency_limit: int = 8
    tool_concurrency_limit: int = 16
    agent_llm_stream_timeout_seconds: float = Field(
        default=180.0,
        validation_alias=AliasChoices(
            "AGENT_LLM_STREAM_TIMEOUT_SECONDS",
            "agent_llm_stream_timeout_seconds",
        ),
    )
    agent_tool_phase_timeout_seconds: float = Field(
        default=240.0,
        validation_alias=AliasChoices(
            "AGENT_TOOL_PHASE_TIMEOUT_SECONDS",
            "agent_tool_phase_timeout_seconds",
        ),
    )
    chat_sse_queue_max: int = Field(
        default=256,
        validation_alias=AliasChoices(
            "CHAT_SSE_QUEUE_MAX",
            "chat_sse_queue_max",
            "DETACHED_RUN_SUBSCRIBER_QUEUE_MAX",
            "detached_run_subscriber_queue_max",
        ),
    )
    host_file_tools_restrict_to_workspace: bool = True
    chat_compact_tool_context: bool = Field(
        default=True,
        validation_alias=AliasChoices("CHAT_COMPACT_TOOL_CONTEXT", "chat_compact_tool_context"),
    )
    chat_openai_native_tools: bool = Field(
        default=True,
        validation_alias=AliasChoices("CHAT_OPENAI_NATIVE_TOOLS", "chat_openai_native_tools"),
    )

    llm_provider: str = "fireworks"
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    chat_model_options: str = ""
    fireworks_api_key: str = os.environ.get("FIREWORKS_API_KEY", "")
    fireworks_base_url: str = "https://api.fireworks.ai/inference/v1"
    fireworks_model: str = "accounts/fireworks/models/kimi-k2p6"
    llm_openai_compat_ids: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_OPENAI_COMPAT_IDS", "llm_openai_compat_ids"),
    )
    llm_openai_compat_json: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_OPENAI_COMPAT_JSON", "llm_openai_compat_json"),
    )

    llm_max_retries: int = 5
    llm_retry_base_seconds: float = 1.5
    max_tokens: int = 4096
    max_steps: int = 15
    research_max_steps: int = 100
    chat_turn_wall_seconds_standard: float = Field(
        default=180.0,
        validation_alias=AliasChoices("CHAT_TURN_WALL_SECONDS_STANDARD", "chat_turn_wall_seconds_standard"),
    )
    chat_turn_wall_seconds_quick: float = Field(
        default=75.0,
        validation_alias=AliasChoices("CHAT_TURN_WALL_SECONDS_QUICK", "chat_turn_wall_seconds_quick"),
    )
    chat_turn_wall_seconds_integration: float = Field(
        default=120.0,
        validation_alias=AliasChoices(
            "CHAT_TURN_WALL_SECONDS_INTEGRATION",
            "chat_turn_wall_seconds_integration",
        ),
    )
    chat_turn_wall_seconds_research: float = Field(
        default=600.0,
        validation_alias=AliasChoices("CHAT_TURN_WALL_SECONDS_RESEARCH", "chat_turn_wall_seconds_research"),
    )
    chat_max_rounds_standard: int = Field(
        default=32,
        validation_alias=AliasChoices("CHAT_MAX_ROUNDS_STANDARD", "chat_max_rounds_standard"),
    )
    chat_max_rounds_integration: int = Field(
        default=18,
        validation_alias=AliasChoices("CHAT_MAX_ROUNDS_INTEGRATION", "chat_max_rounds_integration"),
    )
    agent_loop_warn_round_fraction: float = Field(
        default=0.85,
        validation_alias=AliasChoices("AGENT_LOOP_WARN_ROUND_FRACTION", "agent_loop_warn_round_fraction"),
    )
    chat_prefetch_learned_memory: bool = Field(
        default=True,
        validation_alias=AliasChoices("CHAT_PREFETCH_LEARNED_MEMORY", "chat_prefetch_learned_memory"),
    )
    agent_worker_heartbeat_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices("AGENT_WORKER_HEARTBEAT_SECONDS", "agent_worker_heartbeat_seconds"),
    )
    agent_llm_stream_heartbeat_seconds: float = Field(
        default=12.0,
        validation_alias=AliasChoices("AGENT_LLM_STREAM_HEARTBEAT_SECONDS", "agent_llm_stream_heartbeat_seconds"),
    )
    max_tool_result_chars: int = 48_000
    temperature: float = 0.5
    top_p: float = 0.85
    top_k: int = 20

    exa_api_key: str = os.environ.get("EXA_API_KEY", os.environ.get("AGENT_EXA_API_KEY", ""))
    firecrawl_api_key: str = os.environ.get("FIRECRAWL_API_KEY", os.environ.get("AGENT_FIRECRAWL_API_KEY", ""))

    composio_api_key: str = ""
    composio_user_id: str = "koraku-local"
    composio_tools_limit: int = 48
    composio_subagent_mode: bool = True
    composio_subagent_max_steps: int = 16
    composio_subagent_max_steps_simple: int = Field(
        default=6,
        validation_alias=AliasChoices("COMPOSIO_SUBAGENT_MAX_STEPS_SIMPLE", "composio_subagent_max_steps_simple"),
    )
    composio_subagent_max_steps_compose: int = Field(
        default=10,
        validation_alias=AliasChoices("COMPOSIO_SUBAGENT_MAX_STEPS_COMPOSE", "composio_subagent_max_steps_compose"),
    )
    composio_subagent_wall_seconds: float = Field(
        default=150.0,
        validation_alias=AliasChoices("COMPOSIO_SUBAGENT_WALL_SECONDS", "composio_subagent_wall_seconds"),
    )
    composio_subagent_wall_seconds_simple: float = Field(
        default=90.0,
        validation_alias=AliasChoices(
            "COMPOSIO_SUBAGENT_WALL_SECONDS_SIMPLE",
            "composio_subagent_wall_seconds_simple",
        ),
    )
    composio_subagent_wall_seconds_compose: float = Field(
        default=120.0,
        validation_alias=AliasChoices(
            "COMPOSIO_SUBAGENT_WALL_SECONDS_COMPOSE",
            "composio_subagent_wall_seconds_compose",
        ),
    )

    enable_bash: bool = True
    enable_web_search: bool = True
    enable_web_fetch: bool = True
    enable_file_ops: bool = True
    web_timeout: int = 15
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    )

    agent_name: str = "koraku-agent"
    version: str = "1.0.0"
    chat_quick_max_steps: int = Field(
        default=4,
        validation_alias=AliasChoices("CHAT_QUICK_MAX_STEPS", "chat_quick_max_steps"),
    )
    permission_mode: str = Field(
        default="default",
        validation_alias=AliasChoices("PERMISSION_MODE", "KORAKU_PERMISSION_MODE", "permission_mode"),
    )
    enable_ask_user: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_ASK_USER", "enable_ask_user"),
    )
    ask_user_timeout_seconds: float = Field(
        default=600.0,
        validation_alias=AliasChoices("ASK_USER_TIMEOUT_SECONDS", "ask_user_timeout_seconds"),
    )
    subagent_max_steps: int = Field(
        default=24,
        validation_alias=AliasChoices("SUBAGENT_MAX_STEPS", "subagent_max_steps"),
    )
    subagent_max_depth: int = Field(
        default=1,
        validation_alias=AliasChoices("SUBAGENT_MAX_DEPTH", "subagent_max_depth"),
    )
    subagent_wall_seconds: float = Field(
        default=180.0,
        validation_alias=AliasChoices("SUBAGENT_WALL_SECONDS", "subagent_wall_seconds"),
    )
    enable_run_artifacts: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_RUN_ARTIFACTS", "enable_run_artifacts"),
    )
    enable_mcp: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_MCP", "enable_mcp"),
    )
    enable_propose_action: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_PROPOSE_ACTION", "enable_propose_action"),
    )

    # HTTP server / self-host
    redis_url: str = Field(
        default="",
        validation_alias=AliasChoices("REDIS_URL", "redis_url"),
    )
    require_auth_for_chat: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "REQUIRE_AUTH_FOR_CHAT",
            "__koraku_require_auth_for_chat",
        ),
    )
    auth_backend: str = Field(
        default="none",
        validation_alias=AliasChoices("AUTH_BACKEND", "KORAKU_AUTH_BACKEND", "auth_backend"),
    )
    koraku_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("KORAKU_API_KEY", "koraku_api_key"),
    )
    health_detail_token: str = Field(
        default="",
        validation_alias=AliasChoices("HEALTH_DETAIL_TOKEN", "health_detail_token"),
    )
    chat_rate_limit_per_minute: int = Field(
        default=12,
        validation_alias=AliasChoices("CHAT_RATE_LIMIT_PER_MINUTE", "chat_rate_limit_per_minute"),
    )
    automation_rate_limit_per_minute: int = Field(
        default=6,
        validation_alias=AliasChoices("AUTOMATION_RATE_LIMIT_PER_MINUTE", "automation_rate_limit_per_minute"),
    )
    automation_manual_run_concurrency_per_user: int = Field(
        default=1,
        validation_alias=AliasChoices(
            "AUTOMATION_MANUAL_RUN_CONCURRENCY_PER_USER",
            "automation_manual_run_concurrency_per_user",
        ),
    )
    automation_scheduler_enabled: bool = True
    automation_scheduler_resync_seconds: int = 60
    automation_max_steps: int = 12
    automation_run_timeout_seconds: float = 180.0
    supermemory_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPERMEMORY_API_KEY", "supermemory_api_key"),
    )
    supermemory_context_max_chars: int = Field(
        default=6_000,
        validation_alias=AliasChoices(
            "SUPERMEMORY_CONTEXT_MAX_CHARS",
            "supermemory_context_max_chars",
        ),
    )
    learned_memory_cache_ttl_seconds: float = Field(
        default=90.0,
        validation_alias=AliasChoices(
            "LEARNED_MEMORY_CACHE_TTL_SECONDS",
            "learned_memory_cache_ttl_seconds",
        ),
    )
    chat_learned_memory_timeout_seconds: float = Field(
        default=4.0,
        validation_alias=AliasChoices(
            "CHAT_LEARNED_MEMORY_TIMEOUT_SECONDS",
            "chat_learned_memory_timeout_seconds",
        ),
    )
    blaxel_sandbox_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("BLAXEL_SANDBOX_ENABLED", "blaxel_sandbox_enabled"),
    )
    bl_workspace: str = Field(default="", validation_alias=AliasChoices("BL_WORKSPACE", "bl_workspace"))
    bl_api_key: str = Field(default="", validation_alias=AliasChoices("BL_API_KEY", "bl_api_key"))
    blaxel_sandbox_image: str = "blaxel/base-image:latest"
    blaxel_sandbox_region: str = "us-pdx-1"
    blaxel_sandbox_memory_mb: int = 512
    blaxel_sandbox_workdir: str = "/tmp"
    blaxel_sandbox_ready_timeout_seconds: float = 120.0
    blaxel_sandbox_cache_ttl_seconds: float = Field(
        default=600.0,
        validation_alias=AliasChoices(
            "BLAXEL_SANDBOX_CACHE_TTL_SECONDS",
            "blaxel_sandbox_cache_ttl_seconds",
        ),
    )
    chat_defer_blaxel_provision: bool = Field(
        default=True,
        validation_alias=AliasChoices("CHAT_DEFER_BLAXEL_PROVISION", "chat_defer_blaxel_provision"),
    )
    composio_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("COMPOSIO_WEBHOOK_SECRET", "composio_webhook_secret"),
    )
    composio_webhook_auto_setup: bool = Field(
        default=False,
        validation_alias=AliasChoices("COMPOSIO_WEBHOOK_AUTO_SETUP", "composio_webhook_auto_setup"),
    )

    def model_post_init(self, __context: Any) -> None:
        key = (self.bl_api_key or "").strip()
        ws = (self.bl_workspace or "").strip()
        if key:
            os.environ["BL_API_KEY"] = key
        if ws:
            os.environ["BL_WORKSPACE"] = ws

    @property
    def cors_origins_list(self) -> list[str]:
        raw = (self.cors_allowed_origins or "").strip()
        if not raw:
            return []
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]

    @property
    def trusted_proxy_cidrs_list(self) -> list[str]:
        raw = (self.trusted_proxy_cidrs or "").strip()
        if not raw:
            return []
        return [c.strip() for c in raw.split(",") if c.strip()]
