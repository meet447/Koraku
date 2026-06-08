"""Developer-facing helpers for configuring LLM providers."""
from __future__ import annotations

from typing import Any

from koraku.llm.catalog import (
    any_llm_configured,
    configured_provider_ids,
    default_chat_model,
    default_model_for_provider,
    is_provider_configured,
    known_provider_ids,
    ui_chat_models,
)
from koraku.llm.openai_compat_registry import (
    OpenAICompatProvider,
    clear_runtime_openai_compat_providers,
    get_openai_compat_provider,
    load_openai_compat_providers,
    register_openai_compat_provider,
    register_openai_compat_providers,
)


def list_providers(*, detailed: bool = False) -> list[dict[str, Any]] | list[str]:
    """Return configured provider ids, or UI-shaped blocks when ``detailed=True``."""
    if detailed:
        return list(ui_chat_models().get("providers") or [])
    return configured_provider_ids()


def describe_provider(provider_id: str) -> dict[str, Any] | None:
    """Metadata for one provider (built-in or OpenAI-compatible)."""
    pid = (provider_id or "").strip().lower()
    if not pid:
        return None
    if pid in ("anthropic", "fireworks"):
        for block in ui_chat_models().get("providers") or []:
            if block.get("id") == pid:
                return block
        return None
    compat = get_openai_compat_provider(pid)
    if compat is None:
        return None
    return {
        "id": compat.id,
        "label": compat.label,
        "configured": is_provider_configured(pid),
        "default_model": compat.default_model,
        "models": list(compat.models),
    }


__all__ = [
    "OpenAICompatProvider",
    "any_llm_configured",
    "clear_runtime_openai_compat_providers",
    "configured_provider_ids",
    "default_chat_model",
    "default_model_for_provider",
    "describe_provider",
    "get_openai_compat_provider",
    "is_provider_configured",
    "known_provider_ids",
    "list_providers",
    "load_openai_compat_providers",
    "register_openai_compat_provider",
    "register_openai_compat_providers",
    "ui_chat_models",
]
