"""Supabase chat history row trimming and mapping."""

from __future__ import annotations

from src.integrations.supabase_chat_history import (
    db_message_rows_to_agent_messages,
    trim_persisted_rows_for_incoming_message,
)


def test_trim_removes_placeholder_user_assistant_pair() -> None:
    rows = [
        {"role": "user", "content_json": {"text": "first"}},
        {"role": "assistant", "content_json": {"run": {"assistantMarkdown": "Done."}}},
        {"role": "user", "content_json": {"text": "second q"}},
        {
            "role": "assistant",
            "content_json": {"run": {"assistantMarkdown": "", "error": None}},
        },
    ]
    out = trim_persisted_rows_for_incoming_message(rows, "second q")
    assert len(out) == 2
    assert out[-1]["role"] == "assistant"


def test_trim_does_not_remove_distinct_repeat_text() -> None:
    rows = [
        {"role": "user", "content_json": {"text": "hi"}},
        {"role": "assistant", "content_json": {"run": {"assistantMarkdown": "Hello."}}},
    ]
    out = trim_persisted_rows_for_incoming_message(rows, "hi")
    assert len(out) == 2


def test_db_rows_to_agent_messages() -> None:
    msgs = db_message_rows_to_agent_messages(
        [
            {"role": "user", "content_json": {"text": "Q?"}},
            {"role": "assistant", "content_json": {"run": {"assistantMarkdown": "**A**"}}},
        ],
    )
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"
