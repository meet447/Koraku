"""Unified LLM client: pick a streaming backend and normalize request/response.

Providers:
- anthropic: native Messages API + tools (:class:`AnthropicMessagesBackend`)
- fireworks / custom_openai: OpenAI-compatible ``POST /v1/chat/completions`` (streaming SSE).

All paths use :class:`src.llm.canonical.CanonicalChatRequest` for the outbound request and emit
the same normalized stream event shapes (see ``src/llm/canonical.py`` module docstring).
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from src.core.config import settings
from src.core.models import AgentMessage
from src.llm.canonical import CanonicalChatRequest, build_compact_tool_prompt
from src.llm.providers.anthropic_backend import AnthropicMessagesBackend
from src.llm.providers.openai_compat_backend import OpenAICompatBackend

BONSAI_PUBLIC_API_BASE = "https://prism-ml-bonsai-demo.hf.space/v1"


class UnifiedLLMClient:
    """Routes to Anthropic or OpenAI-compatible backends via a shared canonical request."""

    def __init__(self, provider_override: str | None = None, *, custom_base_url: str | None = None) -> None:
        self.provider = (provider_override or settings.llm_provider or "fireworks").strip().lower()
        if self.provider == "anthropic":
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.model = settings.anthropic_model
            self._backend = AnthropicMessagesBackend(self._client)
        elif self.provider == "fireworks":
            self.model = settings.fireworks_model
            self._backend = OpenAICompatBackend(
                base_url=settings.fireworks_base_url,
                api_key=settings.fireworks_api_key,
                timeout=120.0,
            )
        elif self.provider == "custom_openai":
            cm = (settings.custom_model or "").strip()
            self.model = cm or "Ternary-Bonsai-8B-Q2_0"
            resolved = (custom_base_url or settings.custom_base_url or "").strip().rstrip("/")
            base = resolved or BONSAI_PUBLIC_API_BASE.rstrip("/")
            self._backend = OpenAICompatBackend(
                base_url=base,
                api_key=(settings.custom_api_key or "").strip(),
                timeout=120.0,
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def build_compact_tool_prompt(self, tools: list[Any]) -> str:
        """Ultra-compact tool prompt for small models (delegates to canonical builder)."""
        return build_compact_tool_prompt(tools)

    async def stream(
        self,
        messages: list[AgentMessage],
        tool_schemas: list[Any],
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        model_id = (model or "").strip() or self.model
        req = CanonicalChatRequest.for_turn(
            model_id=model_id,
            messages=messages,
            tool_schemas=tool_schemas,
            system_prompt=system_prompt,
        )
        async for ev in self._backend.stream(req):
            yield ev
