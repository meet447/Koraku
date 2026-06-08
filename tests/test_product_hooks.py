"""Product hooks: SDK default path."""
from __future__ import annotations

import pytest

from koraku.api.sdk_session_hydration import hydrate_sdk_session_for_turn
from koraku.core.models import AgentMessage, SessionState
from koraku.core.product_hooks import clear_product_hooks, hydrate_session_for_turn, product_hooks_active


@pytest.mark.asyncio
async def test_sdk_hydration_without_product_hooks() -> None:
    clear_product_hooks()
    session = SessionState(session_id="s1")
    report = await hydrate_session_for_turn(
        session,
        incoming_user_text="hi",
        auth_sub=None,
    )
    assert report.reason == "sdk_empty"
    assert not product_hooks_active()


@pytest.mark.asyncio
async def test_sdk_module_unchanged_for_embedders() -> None:
    session = SessionState(session_id="s2")
    session.messages.append(
        AgentMessage(role="user", content=[{"type": "text", "text": "prior"}])
    )
    report = await hydrate_sdk_session_for_turn(
        session,
        incoming_user_text="next",
        auth_sub=None,
    )
    assert report.reason == "warm"
    assert report.messages_loaded == 1
