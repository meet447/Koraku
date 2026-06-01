"""Agent run context: workspace resolution, tool policy, and chat execution modes."""
from __future__ import annotations

import os

import pytest

from types import SimpleNamespace

from koraku.agent.runtime_context import AgentRunContext, resolve_agent_workspace, resolve_execution_target
from koraku.integrations.blaxel_runtime import session_workspace_root_posix, user_sandbox_name
from koraku.tools.registry import bash_tool, tools_for_execution_target


def test_user_sandbox_name_sanitizes_user_id() -> None:
    assert user_sandbox_name("dev-user-1") == "koraku-user-devuser1"
    assert user_sandbox_name("a_b_c").startswith("koraku-user-")


def test_session_workspace_contains_user_and_session() -> None:
    s = SimpleNamespace(blaxel_sandbox_workdir="/tmp")
    sid = "550e8400-e29b-41d4-a716-446655440000"
    p = session_workspace_root_posix("dev-user-1", sid, s)
    assert p == f"/tmp/koraku/users/dev-user-1/sessions/{sid}"


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
    from koraku.api.chat_routes import StreamChatBody

    assert StreamChatBody(msg="hello").execution_target == "cloud"
    assert StreamChatBody(msg="hello", execution_target="local").execution_target == "local"
    assert StreamChatBody(msg="hello", execution_target="server").execution_target == "server"
    b = StreamChatBody(msg="hello", execution_target="bogus")  # type: ignore[arg-type]
    assert b.execution_target == "cloud"


def test_stream_chat_body_accepts_client_history() -> None:
    from koraku.api.chat_routes import StreamChatBody

    b = StreamChatBody(
        msg="send sarthak this news",
        client_history=[
            {"role": "user", "text": "fetch latest news and save it as md"},
            {"role": "assistant", "text": "Saved latest_news_2026-04-25.md"},
        ],
    )
    assert len(b.client_history) == 2
    assert b.client_history[1].role == "assistant"


def test_stream_local_in_process_when_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    import koraku.api.chat_routes as chat_routes
    from koraku.server import app

    monkeypatch.setattr(chat_routes.settings, "require_auth_for_chat", False, raising=False)
    monkeypatch.setattr(chat_routes.settings, "allow_local_execution_in_chat", True, raising=False)
    client = TestClient(app)
    with client.stream("POST", "/stream", json={"msg": "hi", "execution_target": "local"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "koraku.started" in body


def test_stream_local_disabled_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    import koraku.api.chat_routes as chat_routes
    from koraku.server import app

    monkeypatch.setattr(chat_routes.settings, "require_auth_for_chat", False, raising=False)
    monkeypatch.setattr(chat_routes.settings, "allow_local_execution_in_chat", False, raising=False)
    client = TestClient(app)
    resp = client.post("/stream", json={"msg": "hi", "execution_target": "local"})
    assert resp.status_code == 503


def test_stream_local_when_linked_desktop_returns_501(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    import koraku.api.chat_routes as chat_routes
    from koraku.server import app

    monkeypatch.setattr(chat_routes.settings, "require_auth_for_chat", False, raising=False)
    monkeypatch.setattr(chat_routes.settings, "allow_local_execution_in_chat", True, raising=False)
    monkeypatch.setattr(
        "koraku.api.execution_policy.chat_local_execution_available",
        lambda _r: True,
    )
    client = TestClient(app)
    resp = client.post("/stream", json={"msg": "hi", "execution_target": "local"})
    assert resp.status_code == 501


def test_stream_cloud_blaxel_blocked_sse_has_completed_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blocked cloud must map agent.error through koraku_sse so the web client shows failure."""
    from fastapi.testclient import TestClient

    import koraku.api.chat_routes as chat_routes
    from koraku.server import app

    monkeypatch.setattr(chat_routes.settings, "require_auth_for_chat", False, raising=False)
    monkeypatch.setattr(chat_routes, "cloud_blaxel_block_reason", lambda _s: "blocked-for-test")
    client = TestClient(app)
    with client.stream("POST", "/stream", json={"msg": "hi"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "koraku.started" in body
    assert "koraku.completed" in body
    assert "blocked-for-test" in body
    assert "event: done" in body
