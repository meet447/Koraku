"""Local filesystem automations for the SDK."""
from __future__ import annotations

import json

import pytest

from koraku.automations import local_store
from koraku.automations.agent_tools import build_automation_tools
from koraku.automations.validation import validate_cron_expression, validate_timezone_iana


@pytest.mark.asyncio
async def test_local_automation_crud(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    tools = {t.name: t for t in build_automation_tools()}
    create_out = await tools["AutomationsCreate"].run(
        title="Morning brief",
        natural_language_spec="Summarize my calendar for today.",
        trigger_mode="scheduled",
        timezone="UTC",
        cron_expression="0 9 * * *",
    )
    assert "Morning brief" in create_out
    data = json.loads(create_out)
    aid = data["automation"]["id"]

    list_out = await tools["AutomationsList"].run()
    listed = json.loads(list_out)
    assert listed["count"] == 1

    update_out = await tools["AutomationsUpdate"].run(
        automation_id=aid,
        status="paused",
    )
    assert '"status": "paused"' in update_out

    delete_out = await tools["AutomationsDelete"].run(automation_id=aid)
    assert json.loads(delete_out)["ok"] is True
    assert local_store.list_automations() == []


def test_cron_validation() -> None:
    assert validate_cron_expression("0 9 * * *") == "0 9 * * *"
    assert validate_timezone_iana("America/New_York") == "America/New_York"
