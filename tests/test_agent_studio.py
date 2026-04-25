"""Agent Studio routing for daily-driver workflows."""

from __future__ import annotations

from src.agent.run import build_system_prompt
from src.agent.studio import build_studio_plan, studio_system_section
from src.streaming.orchids_sse import KorakuStreamState, map_koraku_stream_events


def test_simple_task_uses_direct_mode() -> None:
    plan = build_studio_plan("what is 2+2?")

    assert plan.mode == "direct"
    assert plan.enabled is False
    assert plan.roles[0].name == "Director"


def test_research_workflow_uses_studio_roles_and_artifacts() -> None:
    plan = build_studio_plan(
        "Research three CRM vendors, compare pricing and features, create an Excel-ready table, then draft an email summary."
    )

    role_names = [r.name for r in plan.roles]
    artifact_paths = [a.path for a in plan.artifacts]

    assert plan.mode == "studio"
    assert "Scout" in role_names
    assert "Analyst" in role_names
    assert "Skeptic" in role_names
    assert "Operator" in role_names
    assert "Archivist" in role_names
    assert "sources.json" in artifact_paths
    assert "evidence-table.md" in artifact_paths
    assert "draft-email.md" in artifact_paths
    assert any("approval" in g.lower() for g in plan.approval_gates)


def test_automation_override_uses_studio_mode() -> None:
    plan = build_studio_plan("summarize my inbox", max_steps_override=4)

    assert plan.mode == "studio"
    assert any("automation" in g.lower() for g in plan.approval_gates)


def test_studio_section_lists_task_room_and_artifacts() -> None:
    plan = build_studio_plan("Research competitors and create a brief")
    section = studio_system_section(plan)

    assert "Current turn Agent Studio plan" in section
    assert f".koraku/runs/{plan.run_slug}/" in section
    assert "sources.json" in section


def test_system_prompt_includes_current_studio_section(tmp_path) -> None:
    plan = build_studio_plan("Research competitors and create a brief")
    prompt = build_system_prompt(str(tmp_path), studio_section=studio_system_section(plan))

    assert "personal daily driver" in prompt
    assert "Current turn Agent Studio plan" in prompt
    assert plan.run_slug in prompt


def test_studio_event_maps_to_trace() -> None:
    plan = build_studio_plan("Research competitors and create a brief")
    state = KorakuStreamState()

    rows = map_koraku_stream_events({"type": "agent.studio", "data": plan.to_event_payload()}, state)

    assert len(rows) == 1
    assert rows[0]["type"] == "koraku.event"
    assert '"trace": "studio"' in rows[0]["data"]
