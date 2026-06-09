"""Typed SDK models and interaction helpers."""
from __future__ import annotations

import asyncio

import pytest

from koraku import (
    ActionData,
    ApprovalData,
    CompletedData,
    ErrorData,
    EventType,
    Koraku,
    KorakuConfig,
    KorakuEvent,
    PermissionModes,
    ProviderInfo,
    QuestionData,
    SessionState,
    answer_question,
    approve_tool,
    message_text,
)
from koraku.agent.pending_interactions import register


def test_question_data_from_event() -> None:
    event = KorakuEvent.wrap({
        "type": EventType.agent.question,
        "data": {
            "interaction_id": "q-1",
            "questions": [
                {
                    "header": "Goal",
                    "question": "What for?",
                    "options": [{"label": "Work"}, {"label": "Personal"}],
                }
            ],
        },
    })
    assert event.question is not None
    assert event.question.interaction_id == "q-1"
    assert len(event.question.questions) == 1
    assert event.question.questions[0].options[0].label == "Work"


def test_completed_and_error_payloads() -> None:
    done = KorakuEvent.wrap({
        "type": EventType.agent.completed,
        "data": {"reason": "end_turn", "steps": 3, "mode": "standard"},
    })
    assert done.completed == CompletedData(reason="end_turn", steps=3, mode="standard")

    err = KorakuEvent.wrap({
        "type": EventType.agent.error,
        "data": {"error": "boom", "code": "x"},
    })
    assert err.error == ErrorData(error="boom", code="x")


def test_llm_stream_event_text() -> None:
    delta = KorakuEvent.wrap({
        "type": EventType.stream_event,
        "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}},
    })
    assert delta.llm is not None
    assert delta.llm.text == "Hi"
    assert delta.text == "Hi"


def test_provider_info_from_dict() -> None:
    p = ProviderInfo.from_dict({
        "id": "fireworks",
        "label": "Fireworks",
        "configured": True,
        "default_model": "accounts/fireworks/models/kimi-k2p6",
        "models": ["accounts/fireworks/models/kimi-k2p6"],
    })
    assert p.id == "fireworks"
    assert p.configured is True


def test_message_text_and_session_helpers() -> None:
    text = message_text([{"type": "text", "text": "Hello"}])
    assert text == "Hello"

    session = SessionState(session_id="s1")
    session.add_message("user", "My name is Alex")
    session.add_message("assistant", [{"type": "text", "text": "Hi Alex"}])
    assert session.last_user_text() == "My name is Alex"
    assert session.last_assistant_text() == "Hi Alex"


@pytest.mark.asyncio
async def test_answer_question_and_approve_tool() -> None:
    iid, fut = await register("question", payload={"questions": []})

    async def respond() -> None:
        await asyncio.sleep(0.05)
        answer_question(iid, {"Goal": "Work"})

    task = asyncio.create_task(respond())
    body = await fut
    await task
    assert body["answers"]["Goal"] == "Work"

    iid2, fut2 = await register("approval", payload={"tool": "Bash"})
    assert approve_tool(iid2, approved=False) is True
    body2 = await fut2
    assert body2["approved"] is False


def test_permission_modes_constants() -> None:
    assert PermissionModes.plan == "plan"


def test_action_and_approval_data() -> None:
    action = ActionData.from_dict({
        "action_id": "a1",
        "label": "Run",
        "tool": "Bash",
        "input": {"command": "ls"},
    })
    assert action.tool == "Bash"

    approval = ApprovalData.from_dict({
        "interaction_id": "ap-1",
        "tool": "Write",
        "input": {"path": "x"},
        "tool_use_id": "tu-1",
    })
    assert approval.tool == "Write"
