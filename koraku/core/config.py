"""Runtime settings for the Koraku SDK."""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any, Iterator

from koraku.core.sdk_settings import SdkSettings

# Backward-compatible alias — Settings is SdkSettings (no separate product layer).
Settings = SdkSettings

_default_sdk: SdkSettings | None = None
_settings_override: contextvars.ContextVar[SdkSettings | None] = contextvars.ContextVar(
    "koraku_settings",
    default=None,
)


def get_sdk_settings() -> SdkSettings:
    override = _settings_override.get()
    if override is not None:
        return override
    global _default_sdk
    if _default_sdk is None:
        _default_sdk = SdkSettings()
    return _default_sdk


def configure_sdk(settings_obj: SdkSettings | None = None, **kwargs: Any) -> SdkSettings:
    from koraku.core.auth import reset_auth_verifier
    from koraku.plugins.memory import reset_memory_backend_cache

    global _default_sdk
    if settings_obj is not None:
        _default_sdk = settings_obj
    elif kwargs:
        _default_sdk = get_sdk_settings().model_copy(update=kwargs)
    else:
        _default_sdk = SdkSettings()
    reset_memory_backend_cache()
    reset_auth_verifier()
    return _default_sdk


def get_settings() -> SdkSettings:
    override = _settings_override.get()
    if override is not None:
        return override
    return get_sdk_settings()


class _SettingsProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_settings(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        configure(get_settings().model_copy(update={name: value}))

    def __repr__(self) -> str:
        return repr(get_settings())


settings = _SettingsProxy()


def configure(settings_obj: SdkSettings | None = None, **kwargs: Any) -> SdkSettings:
    from koraku.core.auth import reset_auth_verifier
    from koraku.plugins.memory import reset_memory_backend_cache

    global _default_sdk
    if settings_obj is not None:
        _default_sdk = settings_obj
    elif kwargs:
        _default_sdk = get_settings().model_copy(update=kwargs)
    else:
        _default_sdk = SdkSettings()
    reset_memory_backend_cache()
    reset_auth_verifier()
    return get_settings()


@contextmanager
def use_settings(settings_obj: SdkSettings) -> Iterator[SdkSettings]:
    token = _settings_override.set(settings_obj)
    try:
        yield settings_obj
    finally:
        _settings_override.reset(token)


def runtime_mode_label() -> str:
    return "sdk"
