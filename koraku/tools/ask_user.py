"""AskUser tool — structured clarifying questions with blocking until the user responds."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from koraku.agent.active_run import (
    get_active_ask_user_timeout,
    get_active_emit,
    get_active_run_id,
)
from koraku.agent.pending_interactions import register, wait_for_response
from koraku.tools.tool_def import Tool


def _validate_questions(questions: Any) -> list[dict[str, Any]] | str:
    if not isinstance(questions, list) or not questions:
        return "Error: questions must be a non-empty list."
    if len(questions) > 4:
        return "Error: at most 4 questions per AskUser call."
    normalized: list[dict[str, Any]] = []
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            return f"Error: question {i + 1} must be an object."
        header = str(q.get("header") or "").strip()
        text = str(q.get("question") or q.get("text") or "").strip()
        if not text:
            return f"Error: question {i + 1} needs a non-empty question string."
        options_raw = q.get("options")
        if options_raw is None:
            options_raw = q.get("choices")
        options: list[dict[str, str]] = []
        if options_raw is not None:
            if not isinstance(options_raw, list) or not options_raw:
                return f"Error: question {i + 1} options must be a non-empty list when provided."
            if len(options_raw) > 6:
                return f"Error: question {i + 1} has too many options (max 6)."
            for j, opt in enumerate(options_raw):
                if isinstance(opt, str):
                    label = opt.strip()
                    if not label:
                        return f"Error: option {j + 1} in question {i + 1} is empty."
                    options.append({"label": label, "description": ""})
                elif isinstance(opt, dict):
                    label = str(opt.get("label") or opt.get("value") or "").strip()
                    if not label:
                        return f"Error: option {j + 1} in question {i + 1} needs a label."
                    desc = str(opt.get("description") or "").strip()
                    preview = str(opt.get("preview") or "").strip()
                    item: dict[str, str] = {"label": label, "description": desc}
                    if preview:
                        item["preview"] = preview
                    options.append(item)
                else:
                    return f"Error: invalid option type in question {i + 1}."
        multi = bool(q.get("multiSelect") or q.get("multi_select"))
        normalized.append({
            "header": header or f"Question {i + 1}",
            "question": text,
            "options": options,
            "multiSelect": multi,
        })
    return normalized


async def _ask_user(**kwargs: Any) -> str:
    questions_raw = kwargs.get("questions")
    validated = _validate_questions(questions_raw)
    if isinstance(validated, str):
        return validated

    emit = get_active_emit()
    run_id = get_active_run_id()
    interaction_id, future = await register(
        "question",
        run_id=run_id,
        payload={"questions": validated},
    )
    event = {
        "type": "agent.question",
        "data": {
            "interaction_id": interaction_id,
            "question_id": interaction_id,
            "run_id": run_id or "",
            "questions": validated,
        },
    }
    if emit is not None:
        emit(event)

    try:
        response = await wait_for_response(
            interaction_id,
            future,
            timeout_seconds=get_active_ask_user_timeout(),
        )
    except asyncio.TimeoutError:
        return "Error: AskUser timed out waiting for a user response."

    answers = response.get("answers")
    if not isinstance(answers, dict) or not answers:
        return "Error: user response did not include answers."

    return json.dumps({"ok": True, "answers": answers}, ensure_ascii=False)


ask_user_tool = Tool(
    name="AskUser",
    description=(
        "Ask the user one or more clarifying questions before proceeding. "
        "Each question may include short option labels; the user can pick an option or type a free-text answer. "
        "Use in plan mode or whenever requirements are ambiguous."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "description": "Up to 4 questions.",
                "items": {
                    "type": "object",
                    "properties": {
                        "header": {"type": "string", "description": "Short section title."},
                        "question": {"type": "string", "description": "The question text."},
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "description": {"type": "string"},
                                    "preview": {
                                        "type": "string",
                                        "description": "Optional HTML preview fragment for the option.",
                                    },
                                },
                                "required": ["label"],
                            },
                        },
                        "multiSelect": {
                            "type": "boolean",
                            "description": "Allow multiple option labels (comma-joined in the answer).",
                        },
                    },
                    "required": ["question"],
                },
            },
        },
        "required": ["questions"],
    },
    handler=_ask_user,
    categories=["interaction"],
)
