"""Helpers for consuming Koraku agent stream events in embedder apps."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any

from koraku.core.message_text import message_text
from koraku.sdk_types import (
    ActionData,
    ApprovalData,
    CompletedData,
    ErrorData,
    LlmStreamEvent,
    QuestionData,
    SubagentData,
)

__all__ = [
    "EventType",
    "KorakuEvent",
    "action_payload",
    "assistant_text_blocks",
    "collect_assistant_text",
    "collect_events_assistant_text",
    "collect_stream_events_text",
    "collect_stream_text",
    "event_type",
    "is_action",
    "is_approval",
    "is_completed",
    "is_error",
    "is_question",
    "is_run_log",
    "is_skill_invocation",
    "iter_assistant_text",
    "message_text",
    "parse_event",
    "question_payload",
    "run_log_path",
]


class EventType:
    """Stream event type strings (use with :class:`KorakuEvent`)."""

    stream_event = "stream_event"

    class agent:
        completed = "agent.completed"
        question = "agent.question"
        approval = "agent.approval"
        error = "agent.error"
        cancelled = "agent.cancelled"
        action = "agent.action"
        skill = "agent.skill"
        run_log = "agent.run_log"
        mode = "agent.mode"
        tools = "agent.tools"
        context = "agent.context"
        memory = "agent.memory"
        warning = "agent.warning"
        history = "agent.history"
        subagent = "agent.subagent"
        trace = "agent.trace"


@dataclass(frozen=True)
class KorakuEvent:
    """Typed wrapper around one raw stream event dict from :meth:`Koraku.stream`."""

    raw: dict[str, Any]

    @classmethod
    def wrap(cls, raw: dict[str, Any]) -> KorakuEvent:
        return cls(raw)

    @property
    def type(self) -> str:
        return str(self.raw.get("type") or "")

    @property
    def data(self) -> dict[str, Any]:
        payload = self.raw.get("data")
        return dict(payload) if isinstance(payload, dict) else {}

    @property
    def stream(self) -> dict[str, Any]:
        """Raw inner LLM event when ``type`` is :attr:`EventType.stream_event`."""
        inner = self.raw.get("event")
        return dict(inner) if isinstance(inner, dict) else {}

    @property
    def llm(self) -> LlmStreamEvent | None:
        if not self.is_stream_event:
            return None
        return LlmStreamEvent(self.stream)

    def matches(self, event_type: str) -> bool:
        return self.type == event_type

    @property
    def is_stream_event(self) -> bool:
        return self.type == EventType.stream_event

    @property
    def is_completed(self) -> bool:
        return self.type == EventType.agent.completed

    @property
    def is_error(self) -> bool:
        return self.type == EventType.agent.error

    @property
    def is_question(self) -> bool:
        return self.type == EventType.agent.question

    @property
    def is_approval(self) -> bool:
        return self.type == EventType.agent.approval

    @property
    def is_action(self) -> bool:
        return self.type == EventType.agent.action

    @property
    def is_run_log(self) -> bool:
        return self.type == EventType.agent.run_log

    @property
    def is_subagent(self) -> bool:
        return self.type == EventType.agent.subagent

    @property
    def assistant_text(self) -> list[str]:
        return assistant_text_blocks(self.raw)

    @property
    def text(self) -> str:
        """Concatenated assistant text for this event (stream deltas or full message)."""
        if self.llm is not None:
            t = self.llm.text
            if t:
                return t
        return "".join(self.assistant_text)

    @property
    def interaction_id(self) -> str | None:
        if not self.is_question and not self.is_approval:
            return None
        iid = self.data.get("interaction_id") or self.data.get("question_id") or self.data.get("approval_id")
        return str(iid) if iid else None

    @property
    def questions(self) -> list[dict[str, Any]]:
        """Legacy list-of-dicts view (prefer :attr:`question`)."""
        if not self.is_question:
            return []
        qs = self.data.get("questions")
        return list(qs) if isinstance(qs, list) else []

    @property
    def question(self) -> QuestionData | None:
        if not self.is_question:
            return None
        return QuestionData.from_dict(self.data)

    @property
    def approval(self) -> ApprovalData | None:
        if not self.is_approval:
            return None
        return ApprovalData.from_dict(self.data)

    @property
    def action(self) -> ActionData | None:
        if not self.is_action:
            return None
        return ActionData.from_dict(self.data)

    @property
    def completed(self) -> CompletedData | None:
        if not self.is_completed:
            return None
        return CompletedData.from_dict(self.data)

    @property
    def error(self) -> ErrorData | None:
        if not self.is_error:
            return None
        return ErrorData.from_dict(self.data)

    @property
    def subagent(self) -> SubagentData | None:
        if not self.is_subagent:
            return None
        return SubagentData.from_dict(self.data)

    @property
    def run_log_path(self) -> str | None:
        if not self.is_run_log:
            return None
        path = self.data.get("path")
        return str(path) if path else None


def parse_event(raw: dict[str, Any]) -> KorakuEvent:
    """Wrap a raw event dict as :class:`KorakuEvent`."""
    return KorakuEvent.wrap(raw)


def event_type(event: dict[str, Any]) -> str:
    return str(event.get("type") or "")


def is_completed(event: dict[str, Any]) -> bool:
    return event_type(event) == EventType.agent.completed


def is_error(event: dict[str, Any]) -> bool:
    return event_type(event) == EventType.agent.error


def is_question(event: dict[str, Any]) -> bool:
    return event_type(event) == EventType.agent.question


def is_approval(event: dict[str, Any]) -> bool:
    return event_type(event) == EventType.agent.approval


def is_skill_invocation(event: dict[str, Any]) -> bool:
    return event_type(event) == EventType.agent.skill


def is_action(event: dict[str, Any]) -> bool:
    return event_type(event) == EventType.agent.action


def is_run_log(event: dict[str, Any]) -> bool:
    return event_type(event) == EventType.agent.run_log


def action_payload(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return dict(data) if isinstance(data, dict) else {}


def run_log_path(event: dict[str, Any]) -> str | None:
    wrapped = KorakuEvent.wrap(event)
    return wrapped.run_log_path


def question_payload(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return dict(data) if isinstance(data, dict) else {}


def assistant_text_blocks(event: dict[str, Any]) -> list[str]:
    """Extract text deltas from one ``stream_event`` wrapper."""
    wrapped = KorakuEvent.wrap(event)
    if wrapped.llm is not None:
        t = wrapped.llm.text
        if t:
            return [t]
    return []


def collect_assistant_text(events: Iterable[dict[str, Any]]) -> str:
    """Join assistant text from a sequence of raw agent events."""
    parts: list[str] = []
    for event in events:
        parts.extend(assistant_text_blocks(event))
    return "".join(parts).strip()


def collect_events_assistant_text(events: Iterable[KorakuEvent]) -> str:
    """Join assistant text from wrapped events."""
    parts: list[str] = []
    for event in events:
        if event.text:
            parts.append(event.text)
    return "".join(parts).strip()


async def iter_assistant_text(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    async for event in events:
        for chunk in assistant_text_blocks(event):
            if chunk:
                yield chunk


async def collect_stream_text(events: AsyncIterator[dict[str, Any]]) -> str:
    return collect_assistant_text([event async for event in events])


async def collect_stream_events_text(events: AsyncIterator[KorakuEvent]) -> str:
    return collect_events_assistant_text([event async for event in events])
