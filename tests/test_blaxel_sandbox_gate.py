"""Sandbox chat must not fall back to host disk when Blaxel is not fully configured."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from koraku.integrations import blaxel_runtime as br
from koraku.integrations.runtime_user import (
    effective_auth_user_sub,
    effective_runtime_user_id,
    reset_runtime_user_id,
    set_runtime_user_id,
)
from koraku.core.tenant import reset_tenant_org_id, set_tenant_org_id


def test_blaxel_sandbox_block_reason_requires_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(br, "blaxel_sdk_available", lambda: True)
    s = SimpleNamespace(
        blaxel_sandbox_enabled=True,
        bl_workspace="",
        bl_api_key="secret",
    )
    msg = br.blaxel_sandbox_block_reason(s)
    assert msg is not None
    assert "BL_WORKSPACE" in msg


def test_effective_runtime_user_id_requires_authenticated_user() -> None:
    with pytest.raises(RuntimeError, match="Authenticated"):
        effective_runtime_user_id()


def test_effective_runtime_user_id_from_request_context() -> None:
    t = set_runtime_user_id("jwt-sub-uuid")
    try:
        assert effective_runtime_user_id() == "jwt-sub-uuid"
    finally:
        reset_runtime_user_id(t)


def test_effective_auth_user_sub_ignores_org_storage_scope() -> None:
    """Supabase rows use auth sub; Blaxel paths use org/user — do not mix them."""
    t = set_runtime_user_id("9c77f10c-fc6a-402f-8749-e3e65779b688")
    org_t = set_tenant_org_id("21ccb3a7-6567-49ea-9885-094673275af2")
    try:
        assert (
            effective_runtime_user_id()
            == "21ccb3a7-6567-49ea-9885-094673275af2/9c77f10c-fc6a-402f-8749-e3e65779b688"
        )
        assert effective_auth_user_sub() == "9c77f10c-fc6a-402f-8749-e3e65779b688"
    finally:
        reset_tenant_org_id(org_t)
        reset_runtime_user_id(t)


def test_automation_agent_tools_use_local_store(tmp_path, monkeypatch) -> None:
    """Local SDK automations do not require auth sub or org."""
    monkeypatch.chdir(tmp_path)
    from koraku.automations.agent_tools import build_automation_tools

    tools = {t.name: t for t in build_automation_tools()}
    assert "AutomationsList" in tools


def test_blaxel_sandbox_block_reason_ok_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(br, "blaxel_sdk_available", lambda: True)
    s = SimpleNamespace(
        blaxel_sandbox_enabled=True,
        bl_workspace="my-ws",
        bl_api_key="secret",
    )
    assert br.blaxel_sandbox_block_reason(s) is None


def test_blaxel_auth_failure_detector_401() -> None:
    class R:
        status_code = 401
        text = ""

    e = Exception("nope")
    e.response = R()  # type: ignore[attr-defined]
    assert br._blaxel_error_looks_like_auth_failure(e)


def test_blaxel_auth_failure_detector_message() -> None:
    assert br._blaxel_error_looks_like_auth_failure(RuntimeError("Authorization failed"))


def test_settings_post_init_exports_blaxel_to_os(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blaxel SDK reads ``os.environ``; Koraku must mirror pydantic-loaded values there."""
    from koraku.core.config import Settings

    monkeypatch.delenv("BL_API_KEY", raising=False)
    monkeypatch.delenv("BL_WORKSPACE", raising=False)
    Settings(bl_api_key="koraku-test-key", bl_workspace="koraku-test-ws")
    assert os.environ["BL_API_KEY"] == "koraku-test-key"
    assert os.environ["BL_WORKSPACE"] == "koraku-test-ws"
