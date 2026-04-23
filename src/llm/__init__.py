"""LLM client, model catalog, and stream parsing helpers."""
from __future__ import annotations

from src.llm.catalog import any_llm_configured, configured_provider_ids, default_chat_model
from src.llm.client import UnifiedLLMClient, _accumulate_openai_tool_call_deltas, _tool_call_slots_to_blocks

__all__ = [
    "UnifiedLLMClient",
    "_accumulate_openai_tool_call_deltas",
    "_tool_call_slots_to_blocks",
    "any_llm_configured",
    "configured_provider_ids",
    "default_chat_model",
]
