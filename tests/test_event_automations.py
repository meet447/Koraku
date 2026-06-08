"""Event-triggered automations."""
from __future__ import annotations

import json

import pytest

from koraku.automations import local_store
from koraku.automations.agent_tools import build_automation_tools
from koraku.automations.event_triggers import find_automations_for_event


@pytest.mark.asyncio
async def test_event_automation_create(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    tools = {t.name: t for t in build_automation_tools()}
    out = await tools["AutomationsCreate"].run(
        title="On webhook",
        natural_language_spec="Do the thing.",
        trigger_mode="event",
        event_key="inbox-updated",
        event_secret="sekrit",
    )
    data = json.loads(out)
    assert data["automation"]["trigger_mode"] == "event"
    assert find_automations_for_event("inbox-updated")


@pytest.mark.asyncio
async def test_scheduled_create_requires_cron(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    tools = {t.name: t for t in build_automation_tools()}
    out = await tools["AutomationsCreate"].run(
        title="Bad cron",
        natural_language_spec="x",
        trigger_mode="scheduled",
    )
    assert out.startswith("Error:")
