"""Phase A/B: reliability settings, health visibility, log redaction."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.core.config import settings
from src.server import app


def test_settings_has_agent_timeout_fields() -> None:
    assert settings.agent_llm_stream_timeout_seconds >= 30
    assert settings.agent_tool_phase_timeout_seconds >= 30


def test_health_includes_reliability_and_sandbox_fields() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "agent_llm_stream_timeout_seconds" in data
    assert "agent_tool_phase_timeout_seconds" in data
    assert "blaxel_cloud_sandbox_enabled" in data
    assert "cloud_chat_sandbox_block_reason" in data
