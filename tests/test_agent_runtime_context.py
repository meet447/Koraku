"""Agent run context: workspace resolution, tool policy, and chat execution modes."""
from __future__ import annotations

import os

import pytest

from src.agent.runtime_context import AgentRunContext, resolve_agent_workspace, resolve_execution_target
from src.integrations.blaxel_runtime import chat_sandbox_name
from src.tools.registry import bash_tool, tools_for_execution_target


def test_chat_sandbox_name_sanitizes_session_id() -> None:
    assert chat_sandbox_name("550e8400-e29b-41d4-a716-446655440000").startswith("koraku-")
    assert "-" not in chat_sandbox_name("a-b-c")[7:]  # suffix after koraku-


def test_resolve_agent_workspace_explicit_wins() -> None:
    ctx = AgentRunContext(workspace_root="/tmp/from-context")
    assert resolve_agent_workspace("/tmp/explicit", ctx) == os.path.abspath("/tmp/explicit")


def test_resolve_agent_workspace_from_context() -> None:
    ctx = AgentRunContext(workspace_root="/tmp/ws")
    assert resolve_agent_workspace(None, ctx) == os.path.abspath("/tmp/ws")


def test_resolve_execution_target_explicit() -> None:
    assert resolve_execution_target(AgentRunContext(execution_target="cloud")) == "cloud"
    assert resolve_execution_target(None) == "server"


def test_tools_for_execution_target_cloud_excludes_bash() -> None:
    cloud_names = {t.name for t in tools_for_execution_target("cloud")}
    assert "Bash" not in cloud_names
    cloud_with_blaxel = {t.name for t in tools_for_execution_target("cloud", blaxel_sandbox_active=True)}
    assert bash_tool.name in cloud_with_blaxel
    server_names = {t.name for t in tools_for_execution_target("server")}
    assert bash_tool.name in server_names


def test_stream_chat_body_only_cloud_or_local() -> None:
    from src.api.chat_routes import StreamChatBody

    assert StreamChatBody(msg="hello").execution_target == "cloud"
    assert StreamChatBody(msg="hello", execution_target="local").execution_target == "local"
    b = StreamChatBody(msg="hello", execution_target="server")  # type: ignore[arg-type]
    assert b.execution_target == "cloud"


def test_stream_local_without_device_returns_503() -> None:
    from fastapi.testclient import TestClient

    from src.server import app

    client = TestClient(app)
    resp = client.post("/stream", json={"msg": "hi", "execution_target": "local"})
    assert resp.status_code == 503


def test_stream_local_when_linked_stub_returns_501(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    import src.api.chat_routes as chat_routes
    from src.server import app

    monkeypatch.setattr(chat_routes, "chat_local_execution_available", lambda _r: True)
    client = TestClient(app)
    resp = client.post("/stream", json={"msg": "hi", "execution_target": "local"})
    assert resp.status_code == 501


def test_stream_cloud_blaxel_blocked_sse_has_completed_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blocked cloud must map agent.error through orchids_sse so the web client shows failure."""
    from fastapi.testclient import TestClient

    import src.api.chat_routes as chat_routes
    from src.server import app

    monkeypatch.setattr(chat_routes, "cloud_blaxel_block_reason", lambda _s: "blocked-for-test")
    client = TestClient(app)
    with client.stream("POST", "/stream", json={"msg": "hi"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "koraku.started" in body
    assert "koraku.completed" in body
    assert "blocked-for-test" in body
    assert "event: done" in body
