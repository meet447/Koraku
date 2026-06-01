"""Session store backends (memory + Redis REST)."""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from koraku.core.config import Settings, configure, use_settings
from koraku.core.models import SessionState
from koraku.core.session_store import (
    MemorySessionStore,
    RedisSessionStore,
    build_session_store,
    get_session_store,
    reset_session_store,
)


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_session_store()
    yield
    reset_session_store()


def test_memory_store_get_or_create_roundtrip() -> None:
    store = MemorySessionStore()
    tid = str(uuid.uuid4())
    a = store.get_or_create(tid, owner_sub="user-a")
    assert a.session_id == tid
    b = store.get_or_create(tid, owner_sub="user-a")
    assert b is a


def test_memory_store_rejects_other_owner() -> None:
    store = MemorySessionStore()
    tid = str(uuid.uuid4())
    store.get_or_create(tid, owner_sub="user-a").add_message("user", "hi")
    b = store.get_or_create(tid, owner_sub="user-b")
    assert b.owner_sub == "user-b"
    assert b.messages == []


def test_build_session_store_redis_fallback_without_credentials() -> None:
    with use_settings(Settings(session_store_backend="redis", upstash_redis_rest_url="")):
        store = build_session_store()
        assert isinstance(store, MemorySessionStore)


def test_redis_store_save_and_get(monkeypatch: pytest.MonkeyPatch) -> None:
    bucket: dict[str, str] = {}

    def fake_command(self, *args: str):  # type: ignore[no-untyped-def]
        cmd = args[0].upper()
        if cmd == "SET":
            bucket[args[1]] = args[2]
            return "OK"
        if cmd == "GET":
            return bucket.get(args[1])
        if cmd == "DEL":
            bucket.pop(args[1], None)
            return 1
        return None

    monkeypatch.setattr(RedisSessionStore, "_command", fake_command)
    with use_settings(
        Settings(
            session_store_backend="redis",
            upstash_redis_rest_url="https://example.upstash.io",
            upstash_redis_rest_token="token",
        )
    ):
        store = RedisSessionStore()
        session = SessionState(session_id=str(uuid.uuid4()), owner_sub="u1")
        session.add_message("user", "hello")
        store.save(session)
        loaded = store.get(session.session_id)
        assert loaded is not None
        assert loaded.owner_sub == "u1"
        assert len(loaded.messages) == 1


def test_get_session_store_singleton() -> None:
    configure(Settings(session_store_backend="memory"))
    reset_session_store()
    assert get_session_store() is get_session_store()
