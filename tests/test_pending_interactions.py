"""Tests for pending interaction resolve/wait."""
from __future__ import annotations

import asyncio

import pytest

from koraku.agent.pending_interactions import register, resolve, wait_for_response


@pytest.mark.asyncio
async def test_register_resolve_round_trip():
    interaction_id, future = await register("question", run_id="run-1", payload={"q": 1})
    assert interaction_id

    async def _answer_soon() -> None:
        await asyncio.sleep(0.05)
        ok = await resolve(interaction_id, {"answers": {"Tone": "Warm"}})
        assert ok

    asyncio.create_task(_answer_soon())
    body = await wait_for_response(interaction_id, future, timeout_seconds=2.0)
    assert body["answers"]["Tone"] == "Warm"
