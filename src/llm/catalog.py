"""Chat model catalog: Fireworks + Prism Bonsai only (no Anthropic / generic OpenAI presets in UI)."""
import asyncio
from typing import Any

import httpx

from src.core.config import settings

# Public Prism Bonsai Space (no API key)
BONSAI_PUBLIC_API_BASE = "https://prism-ml-bonsai-demo.hf.space/v1"

_FIREWORKS_PRESETS: list[str] = [
    "accounts/fireworks/models/kimi-k2p6",
    "accounts/fireworks/models/minimax-m2p7",
]

_BONSAI_PRISM_PRESETS: list[str] = [
    "Bonsai-8B-Q1_0",
    "Ternary-Bonsai-8B-Q2_0",
]


def _dedupe_preserve(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in ids:
        x = x.strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


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
        return settings.fireworks_model
    return settings.custom_model


def default_chat_model() -> str:
    return default_model_for_provider(None)


def resolve_effective_model(override: str | None, provider_id: str | None = None) -> str:
    o = (override or "").strip()
    if o:
        return o
    return default_model_for_provider(provider_id)


def _filter_fireworks_inference_models(ids: list[str]) -> list[str]:
    prefix = "accounts/fireworks/models/"
    chat = [i for i in ids if i.startswith(prefix)]
    return chat if chat else ids


async def _fetch_v1_model_ids(base_url: str, api_key: str | None = None) -> list[str] | None:
    root = base_url.rstrip("/")
    if not root:
        return None
    headers: dict[str, str] = {"Accept": "application/json"}
    if (api_key or "").strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(f"{root}/v1/models", headers=headers)
            if r.status_code != 200:
                return None
            data = r.json()
            items = data.get("data") or []
            return [str(m["id"]) for m in items if isinstance(m, dict) and m.get("id")] or None
    except Exception:
        return None


async def _catalog_fireworks() -> dict[str, Any]:
    pid = "fireworks"
    configured = is_provider_configured(pid)
    d = default_model_for_provider(pid)
    if configured:
        remote = await _fetch_v1_model_ids(settings.fireworks_base_url, api_key=settings.fireworks_api_key)
        if remote:
            filtered = _filter_fireworks_inference_models(remote)
            if not filtered:
                filtered = remote
            models = _dedupe_preserve([d, *filtered])
        else:
            models = _dedupe_preserve([d, *_FIREWORKS_PRESETS])
    else:
        models = _dedupe_preserve([d, *_FIREWORKS_PRESETS])
    return {"id": pid, "configured": configured, "default_model": d, "models": models}


async def _catalog_bonsai() -> dict[str, Any]:
    """Prism Bonsai via public HF Space or CUSTOM_BASE_URL when it points at Bonsai."""
    pid = "bonsai"
    d = default_model_for_provider(pid)
    base = bonsai_api_base()
    remote = await _fetch_v1_model_ids(base, api_key=None)
    if remote:
        models = _dedupe_preserve([d, *remote])
    else:
        models = _dedupe_preserve([d, *_BONSAI_PRISM_PRESETS])
    return {"id": pid, "configured": True, "default_model": d, "models": models}


def _static_fireworks() -> dict[str, Any]:
    pid = "fireworks"
    cfg = is_provider_configured(pid)
    d = default_model_for_provider(pid)
    return {"id": pid, "configured": cfg, "default_model": d, "models": _dedupe_preserve([d, *_FIREWORKS_PRESETS])}


def _static_bonsai() -> dict[str, Any]:
    d = default_model_for_provider("bonsai")
    return {"id": "bonsai", "configured": True, "default_model": d, "models": _dedupe_preserve([d, *_BONSAI_PRISM_PRESETS])}


def ui_chat_models() -> dict[str, Any]:
    """Sync fallback: Fireworks + Bonsai only."""
    d = default_chat_model()
    raw = (settings.chat_model_options or "").strip()
    active = (settings.llm_provider or "").strip().lower()
    providers = [_static_fireworks(), _static_bonsai()]
    if raw:
        opts = [x.strip() for x in raw.split(",") if x.strip()]
        models = _dedupe_preserve([d, *opts])
        for block in providers:
            if (
                block["id"] == active
                or (active == "custom_openai" and block["id"] == "bonsai")
                or (active == "anthropic" and block["id"] == "fireworks")
            ):
                block["models"] = list(models)
                block["default_model"] = d
        active_block = _pick_active_block(providers, active)
        return {
            "active_provider": active,
            "provider": active,
            "default_model": d,
            "models": models,
            "providers": providers,
        }

    active_block = _pick_active_block(providers, active)
    d2 = active_block["default_model"]
    models2 = active_block["models"]
    return {
        "active_provider": active,
        "provider": active,
        "default_model": d2,
        "models": models2,
        "providers": providers,
    }


def _pick_active_block(providers: list[dict[str, Any]], active: str) -> dict[str, Any]:
    if active == "fireworks":
        return providers[0]
    if active == "custom_openai":
        return providers[1]
    if active == "anthropic":
        if providers[0].get("configured"):
            return providers[0]
        return providers[1]
    return providers[0]


async def ui_chat_models_async() -> dict[str, Any]:
    """Fireworks + Bonsai; live /v1/models where applicable."""
    raw = (settings.chat_model_options or "").strip()
    active = (settings.llm_provider or "").strip().lower()

    fw, bn = await asyncio.gather(_catalog_fireworks(), _catalog_bonsai())
    providers = [fw, bn]

    if raw:
        opts = [x.strip() for x in raw.split(",") if x.strip()]
        d = default_chat_model()
        models = _dedupe_preserve([d, *opts])
        for block in providers:
            if (
                block["id"] == active
                or (active == "custom_openai" and block["id"] == "bonsai")
                or (active == "anthropic" and block["id"] == "fireworks")
            ):
                block["models"] = list(models)
                block["default_model"] = d
        active_block = _pick_active_block(providers, active)
        return {
            "active_provider": active,
            "provider": active,
            "default_model": d,
            "models": models,
            "providers": providers,
        }

    active_block = _pick_active_block(providers, active)
    d = active_block.get("default_model") or default_model_for_provider(active_block["id"])
    models = active_block.get("models") or [d]
    return {
        "active_provider": active,
        "provider": active,
        "default_model": d,
        "models": models,
        "providers": providers,
    }


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
