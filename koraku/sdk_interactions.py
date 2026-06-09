"""Typed helpers for AskUser and tool-approval responses."""
from __future__ import annotations

from typing import Any

from koraku.agent.pending_interactions import respond_to_interaction
from koraku.sdk_types import answer_question_body, approve_tool_body


def answer_question(interaction_id: str, answers: dict[str, str]) -> bool:
    """Submit AskUser answers for an in-process agent run."""
    iid = (interaction_id or "").strip()
    if not iid:
        return False
    return respond_to_interaction(iid, answer_question_body(answers))


def approve_tool(
    interaction_id: str,
    *,
    approved: bool = True,
    updated_input: dict[str, Any] | None = None,
) -> bool:
    """Approve or deny a sensitive tool call (``confirm_sensitive`` mode)."""
    iid = (interaction_id or "").strip()
    if not iid:
        return False
    return respond_to_interaction(iid, approve_tool_body(approved=approved, updated_input=updated_input))
