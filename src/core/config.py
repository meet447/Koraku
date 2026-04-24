"""Configuration and settings for the agent."""
import os
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        # Prefer repo-root ``.env`` so the backend picks up keys even when cwd is not the project root.
        env_file=(str(_REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    # While the model is thinking, emit SSE comment lines so proxies/browsers do not close the stream.
    sse_keepalive_seconds: float = 12.0
    # In-memory chat sessions (/stream): drop after idle TTL; cap total sessions to limit RAM.
    session_ttl_hours: float = 168.0
    session_store_max: int = 2000
    # When True, each LLM call sees user text + assistant visible replies only (tool_use /
    # tool_result pairs from past turns are omitted) to save tokens. Set CHAT_COMPACT_TOOL_CONTEXT=false
    # to send full ReAct traces to the model.
    chat_compact_tool_context: bool = Field(
        default=True,
        validation_alias=AliasChoices("CHAT_COMPACT_TOOL_CONTEXT", "chat_compact_tool_context"),
    )

    # LLM provider: "anthropic" | "fireworks" | "custom_openai"
    llm_provider: str = "fireworks"

    # Anthropic Claude
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # Comma-separated model IDs for the chat UI (optional; defaults to built-in lists per provider)
    chat_model_options: str = ""

    # Fireworks AI (high-quality hosted models)
    fireworks_api_key: str = os.environ.get("FIREWORKS_API_KEY", "")
    fireworks_base_url: str = "https://api.fireworks.ai/inference/v1"
    fireworks_model: str = "accounts/fireworks/models/kimi-k2p6"

    # Custom OpenAI-compatible endpoint (e.g., local llama.cpp)
    custom_base_url: str = ""
    custom_model: str = "gpt-4o-mini"
    custom_api_key: str = os.environ.get("CUSTOM_API_KEY", "")

    # Shared LLM settings
    # Transient errors (429, 502, 503, …): retry POST / stream open with exponential backoff.
    llm_max_retries: int = 5
    llm_retry_base_seconds: float = 1.5
    max_tokens: int = 4096
    max_steps: int = 15
    research_max_steps: int = 100
    # Per tool_result string cap when building the next LLM request (saves tokens; raise for verbose Composio/API JSON).
    max_tool_result_chars: int = 48_000
    temperature: float = 0.5
    top_p: float = 0.85
    top_k: int = 20

    # Premium tools (read without AGENT_ prefix since these are external services)
    exa_api_key: str = os.environ.get("EXA_API_KEY", os.environ.get("AGENT_EXA_API_KEY", ""))
    firecrawl_api_key: str = os.environ.get("FIRECRAWL_API_KEY", os.environ.get("AGENT_FIRECRAWL_API_KEY", ""))

    # Composio (Gmail, Google Drive, Slack, …) — OAuth connections / integrations
    composio_api_key: str = ""
    # Fallback Composio entity id when no signed-in user (JWT) is present (dev / scripts only).
    composio_user_id: str = "koraku-local"
    composio_tools_limit: int = 48
    # Supabase JWT secret (Settings → API) so the backend can verify browser access tokens for
    # per-user Composio linking and tool execution.
    supabase_jwt_secret: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_JWT_SECRET", "supabase_jwt_secret"),
    )
    # PostgREST for ``koraku_automation`` tables (Python API + scheduler). Use the service role key
    # only on the backend; never expose it to the browser.
    supabase_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_URL",
            "NEXT_PUBLIC_SUPABASE_URL",
            "supabase_url",
        ),
    )
    supabase_service_role_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "supabase_service_role_key"),
    )

    @field_validator("supabase_jwt_secret", mode="before")
    @classmethod
    def _strip_supabase_jwt_secret(cls, v: object) -> str:
        """Allow quoted values in ``.env`` without quotes becoming part of the secret."""
        if v is None:
            return ""
        s = str(v).strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            s = s[1:-1].strip()
        return s

    # Tools
    enable_bash: bool = True
    enable_web_search: bool = True
    enable_web_fetch: bool = True
    enable_file_ops: bool = True

    # Web
    web_timeout: int = 15
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

    # Agent identity
    agent_name: str = "koraku-agent"
    version: str = "1.0.0"

    # Saved automations (scheduler + headless agent runs)
    # Set to false on worker-only processes when exactly one leader runs the cron scheduler.
    automation_scheduler_enabled: bool = True
    # How often the leader re-syncs scheduled jobs from Supabase (multi-worker).
    automation_scheduler_resync_seconds: int = 60
    # Tighter cap than chat for scheduled / manual automation runs (cost + safety).
    automation_max_steps: int = 12
    # Wall-clock cap for one automation agent run (LLM + tools).
    automation_run_timeout_seconds: float = 180.0

    # Blaxel sandboxes for chat ``execution_target=cloud`` (isolated file + shell tools).
    # When enabled with BL_WORKSPACE + BL_API_KEY set, each cloud chat session gets a VM; Bash
    # and file tools run there. When disabled or keys missing, cloud chat is refused (no host fallback).
    blaxel_cloud_sandbox_enabled: bool = False
    bl_workspace: str = Field(default="", validation_alias=AliasChoices("BL_WORKSPACE", "bl_workspace"))
    bl_api_key: str = Field(default="", validation_alias=AliasChoices("BL_API_KEY", "bl_api_key"))
    blaxel_sandbox_image: str = "blaxel/base-image:latest"
    blaxel_sandbox_region: str = "us-pdx-1"
    blaxel_sandbox_memory_mb: int = 512
    # Blaxel VM images may not ship ``/home/user``; ``/tmp`` exists on typical Linux sandboxes.
    blaxel_sandbox_workdir: str = "/tmp"
    # Wall-clock cap for Blaxel ``create_if_not_exists`` per chat turn (first bytes still flush via preamble).
    blaxel_sandbox_ready_timeout_seconds: float = 120.0

    @field_validator("bl_workspace", "bl_api_key", mode="before")
    @classmethod
    def _strip_blaxel_credentials(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()

    def model_post_init(self, __context: Any) -> None:
        """The Blaxel SDK authenticates from ``os.environ`` (or ``~/.blaxel/config``), not Pydantic's in-memory merge."""
        key = (self.bl_api_key or "").strip()
        ws = (self.bl_workspace or "").strip()
        if key:
            os.environ["BL_API_KEY"] = key
        if ws:
            os.environ["BL_WORKSPACE"] = ws


settings = Settings()
