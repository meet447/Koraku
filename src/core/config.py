"""Configuration and settings for the agent."""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        # Prefer repo-root ``.env`` so the backend picks up keys even when cwd is not the project root.
        env_file=(str(_REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    # While the model is thinking, emit SSE comment lines so proxies/browsers do not close the stream.
    sse_keepalive_seconds: float = 12.0
    # In-memory chat sessions (/stream): drop after idle TTL; cap total sessions to limit RAM.
    session_ttl_hours: float = 168.0
    session_store_max: int = 2000

    # LLM provider: "anthropic" | "fireworks" | "custom_openai"
    llm_provider: str = "anthropic"

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
    research_max_steps: int = 30
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
    composio_user_id: str = "koraku-local"
    composio_tools_limit: int = 48

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
    # How often the leader re-reads SQLite so other workers' creates/edits pick up (multi-worker + shared DB).
    automation_scheduler_resync_seconds: int = 60
    # Tighter cap than chat for scheduled / manual automation runs (cost + safety).
    automation_max_steps: int = 12
    # Wall-clock cap for one automation agent run (LLM + tools).
    automation_run_timeout_seconds: float = 180.0


settings = Settings()
