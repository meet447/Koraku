"""Helpers for consuming raw Koraku agent stream events in embedder apps."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from typing import Any


def event_type(event: dict[str, Any]) -> str:
    return str(event.get("type") or "")


def is_completed(event: dict[str, Any]) -> bool:
    return event_type(event) == "agent.completed"


def is_error(event: dict[str, Any]) -> bool:
    return event_type(event) == "agent.error"


def is_question(event: dict[str, Any]) -> bool:
    return event_type(event) == "agent.question"


def is_approval(event: dict[str, Any]) -> bool:
    return event_type(event) == "agent.approval"


def is_skill_invocation(event: dict[str, Any]) -> bool:
    return event_type(event) == "agent.skill"


def question_payload(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return dict(data) if isinstance(data, dict) else {}


def assistant_text_blocks(event: dict[str, Any]) -> list[str]:
    """Extract text deltas from one ``stream_event`` wrapper."""
    if event_type(event) != "stream_event":
        return []
    inner = event.get("event")
    if not isinstance(inner, dict):
        return []
    if inner.get("type") == "assistant_message":
        content = (inner.get("message") or {}).get("content")
        if not isinstance(content, list):
            return []
        texts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(str(block.get("text") or ""))
        return texts
    if inner.get("type") == "content_block_delta":
        delta = inner.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta":
            return [str(delta.get("text") or "")]
    return []


def collect_assistant_text(events: Iterable[dict[str, Any]]) -> str:
    """Join assistant text from a sequence of raw agent events."""
    parts: list[str] = []
    for event in events:
        parts.extend(assistant_text_blocks(event))
    return "".join(parts).strip()


async def iter_assistant_text(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    async for event in events:
        for chunk in assistant_text_blocks(event):
            if chunk:
                yield chunk


async def collect_stream_text(events: AsyncIterator[dict[str, Any]]) -> str:
    return collect_assistant_text([event async for event in events])
