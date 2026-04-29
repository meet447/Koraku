"""Phase A/B: reliability settings, health visibility, log redaction."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.core.config import settings
from src.core.redact import redact_mapping, redact_secrets
from src.server import app


def test_redact_secrets_strips_bearer_and_jwt() -> None:
    assert "secret123" not in redact_secrets("Authorization: Bearer secret123")
    jwt = "eyJhbGciOiJIUzI1NiJ.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0zS"
    out = redact_secrets(jwt)
    assert "dozjgNry" not in out
    assert "[REDACTED]" in out


def test_redact_mapping_scrubs_sensitive_keys() -> None:
    d = {"api_key": "sk-test-123456789012345678901234", "ok": "hello"}
    out = redact_mapping(d)
    assert out["api_key"] == "[REDACTED]"
    assert out["ok"] == "hello"


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
