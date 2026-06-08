"""Test defaults: fresh SDK settings for each test."""
from __future__ import annotations

import pytest

from koraku.core.auth import reset_auth_verifier
from koraku.core.config import configure_sdk
from koraku.plugins.memory import reset_memory_backend_cache
from koraku.sdk import KorakuConfig


@pytest.fixture(autouse=True)
def _sdk_settings_for_tests() -> None:
    configure_sdk(KorakuConfig().to_sdk_settings())
    reset_memory_backend_cache()
    reset_auth_verifier()
    yield
    configure_sdk(KorakuConfig().to_sdk_settings())
    reset_memory_backend_cache()
    reset_auth_verifier()
