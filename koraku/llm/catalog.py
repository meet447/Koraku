"""Chat model catalog: Fireworks-only UI (fixed four models with logos)."""
from typing import Any

from koraku.core.config import settings

# Public Prism Bonsai Space (no API key) — agent runtime only; not listed in /api/chat-models.
BONSAI_PUBLIC_API_BASE = "https://prism-ml-bonsai-demo.hf.space/v1"

# Only models exposed in the chat composer (order = UI order).
_FIREWORKS_CURATED: list[dict[str, str]] = [
    {
        "id": "accounts/fireworks/models/kimi-k2p6",
        "logo_url": "https://app.fireworks.ai/images/logos/moonshot-icon.svg",
        "label": "Kimi K2",
    },
    {
        "id": "accounts/fireworks/models/qwen3p6-plus",
        "logo_url": "https://app.fireworks.ai/images/logos/qwen-icon.svg",
        "label": "Qwen3 6 Plus",
    },
    {
        "id": "accounts/fireworks/models/minimax-m2p7",
        "logo_url": "https://app.fireworks.ai/images/logos/minimax-icon.svg",
        "label": "MiniMax M2",
    },
    {
        "id": "accounts/fireworks/models/glm-5p1",
        "logo_url": "https://app.fireworks.ai/images/logos/z-ai.svg",
        "label": "GLM 5.1",
    },
]

_FIREWORKS_CURATED_BY_ID: dict[str, dict[str, str]] = {e["id"]: e for e in _FIREWORKS_CURATED}

_BONSAI_PRISM_PRESETS: list[str] = [
    "Bonsai-8B-Q1_0",
    "Ternary-Bonsai-8B-Q2_0",
]


def _fireworks_curated_ids() -> list[str]:
    return [e["id"] for e in _FIREWORKS_CURATED]


def _normalize_fireworks_model_id(model_id: str | None) -> str:
    m = (model_id or "").strip()
    if m in _FIREWORKS_CURATED_BY_ID:
        return m
    return _fireworks_curated_ids()[0]


def _fireworks_ui_block() -> dict[str, Any]:
    pid = "fireworks"
    configured = is_provider_configured(pid)
    d = _normalize_fireworks_model_id(settings.fireworks_model)
    models = _fireworks_curated_ids()
    entries = [dict(e) for e in _FIREWORKS_CURATED]
    return {
        "id": pid,
        "configured": configured,
        "default_model": d,
        "models": models,
        "entries": entries,
    }


def _is_bonsai_prism_custom() -> bool:
    u = (settings.custom_base_url or "").lower()
    return bool(u) and ("bonsai" in u or "prism-ml-bonsai" in u)


def bonsai_api_base() -> str:
    """OpenAI-compatible base URL for Bonsai (user mirror or public HF demo)."""
    if _is_bonsai_prism_custom():
        return settings.custom_base_url.strip().rstrip("/")
    return BONSAI_PUBLIC_API_BASE.rstrip("/")


def is_provider_configured(provider_id: str) -> bool:
    p = (provider_id or "").strip().lower()
    if p == "bonsai":
        return True
    if p == "anthropic":
        return bool((settings.anthropic_api_key or "").strip())
    if p == "fireworks":
        return bool((settings.fireworks_api_key or "").strip() and (settings.fireworks_base_url or "").strip())
    if p == "custom_openai":
        return bool((settings.custom_base_url or "").strip())
    return False


def default_model_for_provider(provider_id: str | None) -> str:
    p = (provider_id or settings.llm_provider or "fireworks").strip().lower()
    if p == "bonsai":
        if _is_bonsai_prism_custom() and (settings.custom_model or "").strip():
            return settings.custom_model.strip()
        return _BONSAI_PRISM_PRESETS[1]
    if p == "anthropic":
        return settings.anthropic_model
    if p == "fireworks":
        return _normalize_fireworks_model_id(settings.fireworks_model)
    return settings.custom_model


def default_chat_model() -> str:
    return default_model_for_provider(None)


def resolve_effective_model(override: str | None, provider_id: str | None = None) -> str:
    o = (override or "").strip()
    pid = (provider_id or settings.llm_provider or "fireworks").strip().lower()
    if o:
        if pid == "fireworks" and o not in _FIREWORKS_CURATED_BY_ID:
            return _normalize_fireworks_model_id(settings.fireworks_model)
        return o
    return default_model_for_provider(provider_id)


def ui_chat_models() -> dict[str, Any]:
    """Sync: only the four Fireworks models (no remote lists, no other providers)."""
    fw = _fireworks_ui_block()
    return {
        "active_provider": "fireworks",
        "provider": "fireworks",
        "default_model": fw["default_model"],
        "models": fw["models"],
        "providers": [fw],
    }


async def ui_chat_models_async() -> dict[str, Any]:
    """Same as :func:`ui_chat_models` (endpoint stays async for callers)."""
    return ui_chat_models()


def configured_provider_ids() -> list[str]:
    out: list[str] = []
    for pid in ("anthropic", "fireworks", "custom_openai"):
        if is_provider_configured(pid):
            out.append(pid)
    if not out:
        out.append("bonsai")
    return out


def any_llm_configured() -> bool:
    """True when ``configured_provider_ids()`` is non-empty (always true once Bonsai fallback applies)."""
    return len(configured_provider_ids()) > 0
