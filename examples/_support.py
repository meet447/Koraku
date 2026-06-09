"""Shared helpers for example scripts (not part of the installed koraku package)."""
from __future__ import annotations

import sys
from typing import Any

from koraku import KorakuConfig


def require_llm_config(**overrides: Any) -> KorakuConfig:
    """Load config from ``.env`` / environment or exit with setup instructions."""
    cfg = KorakuConfig.from_env(**overrides)
    if not _llm_configured(cfg):
        print(
            "No LLM configured. Copy .env.example to .env and set one of:\n"
            "  FIREWORKS_API_KEY + LLM_PROVIDER=fireworks\n"
            "  ANTHROPIC_API_KEY + LLM_PROVIDER=anthropic\n"
            "  Or see examples/llm_providers.py for OpenAI-compatible endpoints.",
            file=sys.stderr,
        )
        sys.exit(1)
    return cfg


def _llm_configured(cfg: KorakuConfig) -> bool:
    if (cfg.fireworks_api_key or "").strip() or (cfg.anthropic_api_key or "").strip():
        return True
    if cfg.openai_compat_providers:
        return True
    if (cfg.llm_openai_compat_json or "").strip():
        return True
    return False
