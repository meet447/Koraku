"""Detached agent runs: POST /runs + GET /runs/{id}/stream."""

from __future__ import annotations

import re
import asyncio

import pytest
from fastapi.testclient import TestClient

from src.api import detached_runs
from src.server import app


@pytest.fixture(autouse=True)
def _detached_runs_test_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.api.detached_runs._DETACHED_GC_SEC", 0.05, raising=False)

    async def _fake_stream(*_a: object, **_kw: object):
        yield 'data: {"type": "koraku.started", "data": {"chatSessionId": "1234567890123456789012345678"}}\n\n'
        yield "event: done\n\n"

    monkeypatch.setattr("src.api.detached_runs._stream_agent_sse", _fake_stream, raising=False)


def test_runs_post_returns_run_id() -> None:
    client = TestClient(app)
    resp = client.post("/runs", json={"msg": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        data["run_id"],
        re.I,
    )


def test_runs_subscribe_unknown_404() -> None:
    client = TestClient(app)
    rid = "00000000-0000-4000-8000-000000000000"
    resp = client.get(f"/runs/{rid}/stream", params={"after": -1})
    assert resp.status_code == 404


def test_runs_subscribe_streams_sse() -> None:
    client = TestClient(app)
    start = client.post("/runs", json={"msg": "hello"})
    assert start.status_code == 200
    run_id = start.json()["run_id"]
    with client.stream("GET", f"/runs/{run_id}/stream", params={"after": -1}) as r:
        assert r.status_code == 200
        buf = "".join(r.iter_text())
    assert "koraku.started" in buf
    assert "event: done" in buf


@pytest.mark.asyncio
async def test_run_buffer_disconnects_slow_subscriber(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detached_runs, "_SUBSCRIBER_QUEUE_MAX", 1, raising=False)
    buf = detached_runs._RunBuffer(owner_sub=None)
    q: asyncio.Queue[object] = asyncio.Queue(maxsize=1)
    buf.subscribers.append(q)

    await buf.append("data: one\n\n")
    await buf.append("data: two\n\n")

    assert q not in buf.subscribers
