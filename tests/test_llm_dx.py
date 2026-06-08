"""KorakuConfig LLM provider builders and runtime registration."""
from __future__ import annotations

import json

import pytest

from koraku import Koraku, KorakuConfig, OpenAICompatProvider
from koraku.core.config import use_settings
from koraku.llm.client import UnifiedLLMClient
from koraku.llm.openai_compat_registry import (
    clear_runtime_openai_compat_providers,
    get_openai_compat_provider,
    load_openai_compat_providers,
    register_openai_compat_provider,
)


@pytest.fixture(autouse=True)
def _clean_runtime_providers() -> None:
    clear_runtime_openai_compat_providers()
    yield
    clear_runtime_openai_compat_providers()


def test_koraku_config_openai_compat_preset() -> None:
    cfg = KorakuConfig.openai_compat(
        "ollama",
        base_url="http://127.0.0.1:11434/v1",
        model="llama3.2",
    )
    assert cfg.llm_provider == "ollama"
    sdk = cfg.to_sdk_settings()
    assert "ollama" in sdk.llm_openai_compat_json
    assert "11434" in sdk.llm_openai_compat_json


def test_koraku_config_merges_openai_compat_providers() -> None:
    cfg = KorakuConfig(
        llm_provider="groq",
        openai_compat_providers=(
            OpenAICompatProvider(
                id="groq",
                label="Groq",
                base_url="https://api.groq.com/openai/v1",
                api_key="key",
                default_model="llama-3.3-70b-versatile",
                models=("llama-3.3-70b-versatile",),
            ),
        ),
    )
    payload = json.loads(cfg.to_sdk_settings().llm_openai_compat_json)
    assert payload[0]["id"] == "groq"


def test_register_openai_compat_provider_runtime() -> None:
    register_openai_compat_provider(
        OpenAICompatProvider(
            id="local",
            label="Local",
            base_url="http://127.0.0.1:9999/v1",
            api_key="",
            default_model="test-model",
            models=("test-model",),
        )
    )
    assert get_openai_compat_provider("local") is not None


def test_unified_client_unknown_provider_message() -> None:
    with pytest.raises(ValueError, match="register_openai_compat_provider"):
        UnifiedLLMClient(provider_override="does-not-exist")


def test_koraku_list_providers_with_fireworks() -> None:
    agent = Koraku(KorakuConfig.fireworks(api_key="fw-key"))
    with use_settings(agent.settings):
        ids = agent.list_providers()
    assert "fireworks" in ids
