"""In-memory chat session continuity."""

from __future__ import annotations

import importlib
import uuid

import pytest

_sess = importlib.import_module("src.agent.sessions")


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    _sess.sessions.clear()
    yield
    _sess.sessions.clear()


def test_get_or_create_uses_client_uuid_as_session_key() -> None:
    tid = str(uuid.uuid4())
    a = _sess.get_or_create_chat_session(tid)
    assert a.session_id == tid
    assert _sess.sessions[tid] is a
    b = _sess.get_or_create_chat_session(tid)
    assert b is a


def test_get_or_create_no_id_is_random_each_time() -> None:
    a = _sess.get_or_create_chat_session(None)
    b = _sess.get_or_create_chat_session("")
    assert a.session_id != b.session_id
