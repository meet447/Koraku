"""Phase A/B: reliability settings, health visibility, log redaction."""
from __future__ import annotations

from fastapi.testclient import TestClient

from koraku.core.config import settings
from koraku.server_sdk import create_sdk_app


def test_settings_has_agent_timeout_fields() -> None:
    assert settings.agent_llm_stream_timeout_seconds >= 30
    assert settings.agent_tool_phase_timeout_seconds >= 30
    assert settings.cors_origins_list


def test_health_includes_reliability_and_sandbox_fields(monkeypatch) -> None:
    monkeypatch.setattr(settings, "health_detail_token", "test-health-detail")
    client = TestClient(create_sdk_app())
    r = client.get("/health/detail", headers={"Authorization": "Bearer test-health-detail"})
    assert r.status_code == 200
    data = r.json()
    assert "agent_llm_stream_timeout_seconds" in data
    assert "agent_tool_phase_timeout_seconds" in data
    assert "blaxel_cloud_sandbox_enabled" in data
    assert "cloud_chat_sandbox_block_reason" in data
    assert data["runtime"] == "sdk"
    assert "automations_local_configured" in data


def test_request_id_header_is_returned() -> None:
    client = TestClient(create_sdk_app())
    r = client.get("/health", headers={"x-request-id": "req-test-123"})
    assert r.status_code == 200
    assert r.headers["x-request-id"] == "req-test-123"


def test_stream_requires_auth_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_backend", "api_key")
    monkeypatch.setattr(settings, "require_auth_for_chat", True)
    monkeypatch.setattr(settings, "koraku_api_key", "secret-key")
    client = TestClient(create_sdk_app())
    r = client.post("/stream", json={"msg": "hi"})
    assert r.status_code == 401
