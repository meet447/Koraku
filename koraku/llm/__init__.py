"""LLM client, model catalog, and stream parsing helpers."""
from __future__ import annotations

from koraku.llm.canonical import CanonicalChatRequest
from koraku.llm.catalog import any_llm_configured, configured_provider_ids, default_chat_model
from koraku.llm.client import UnifiedLLMClient
from koraku.llm.dx import (
    OpenAICompatProvider,
    describe_provider,
    list_providers,
    register_openai_compat_provider,
    register_openai_compat_providers,
)
from koraku.llm.openai_delta import _accumulate_openai_tool_call_deltas, _tool_call_slots_to_blocks

__all__ = [
    "CanonicalChatRequest",
    "OpenAICompatProvider",
    "UnifiedLLMClient",
    "_accumulate_openai_tool_call_deltas",
    "_tool_call_slots_to_blocks",
    "any_llm_configured",
    "configured_provider_ids",
    "default_chat_model",
    "describe_provider",
    "list_providers",
    "register_openai_compat_provider",
    "register_openai_compat_providers",
]
