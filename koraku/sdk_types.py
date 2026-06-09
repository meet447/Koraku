"""Typed SDK models for events, interactions, providers, and session helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PermissionModeName = Literal["default", "plan", "read_only", "confirm_sensitive"]
ExecutionTargetName = Literal["local", "server", "sandbox"]


class PermissionModes:
    """Permission mode string constants."""

    default: PermissionModeName = "default"
    plan: PermissionModeName = "plan"
    read_only: PermissionModeName = "read_only"
    confirm_sensitive: PermissionModeName = "confirm_sensitive"


class ExecutionTargets:
    """Execution target string constants."""

    local: ExecutionTargetName = "local"
    server: ExecutionTargetName = "server"
    sandbox: ExecutionTargetName = "sandbox"


@dataclass(frozen=True)
class QuestionOption:
    label: str
    description: str = ""
    preview: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> QuestionOption:
        return cls(
            label=str(raw.get("label") or raw.get("value") or "").strip(),
            description=str(raw.get("description") or "").strip(),
            preview=str(raw.get("preview") or "").strip(),
        )


@dataclass(frozen=True)
class Question:
    header: str
    text: str
    options: tuple[QuestionOption, ...] = ()
    multi_select: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Question:
        opts_raw = raw.get("options") if raw.get("options") is not None else raw.get("choices")
        options: list[QuestionOption] = []
        if isinstance(opts_raw, list):
            for item in opts_raw:
                if isinstance(item, str):
                    options.append(QuestionOption(label=item.strip()))
                elif isinstance(item, dict):
                    options.append(QuestionOption.from_dict(item))
        return cls(
            header=str(raw.get("header") or "").strip() or "Question",
            text=str(raw.get("question") or raw.get("text") or "").strip(),
            options=tuple(options),
            multi_select=bool(raw.get("multiSelect") or raw.get("multi_select")),
        )


@dataclass(frozen=True)
class QuestionData:
    interaction_id: str
    run_id: str
    questions: tuple[Question, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuestionData:
        iid = str(data.get("interaction_id") or data.get("question_id") or "").strip()
        qs = data.get("questions")
        questions = tuple(Question.from_dict(q) for q in qs if isinstance(q, dict)) if isinstance(qs, list) else ()
        return cls(
            interaction_id=iid,
            run_id=str(data.get("run_id") or "").strip(),
            questions=questions,
        )


@dataclass(frozen=True)
class ApprovalData:
    interaction_id: str
    tool: str
    tool_input: dict[str, Any]
    run_id: str
    tool_use_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalData:
        iid = str(data.get("interaction_id") or data.get("approval_id") or "").strip()
        return cls(
            interaction_id=iid,
            tool=str(data.get("tool") or "").strip(),
            tool_input=dict(data.get("input") or {}) if isinstance(data.get("input"), dict) else {},
            run_id=str(data.get("run_id") or "").strip(),
            tool_use_id=str(data.get("tool_use_id") or "").strip(),
        )


@dataclass(frozen=True)
class ActionData:
    action_id: str
    label: str
    tool: str
    description: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionData:
        return cls(
            action_id=str(data.get("action_id") or "").strip(),
            label=str(data.get("label") or "").strip(),
            tool=str(data.get("tool") or "").strip(),
            description=str(data.get("description") or "").strip(),
            tool_input=dict(data.get("input") or {}) if isinstance(data.get("input"), dict) else {},
            run_id=str(data.get("run_id") or "").strip(),
        )


@dataclass(frozen=True)
class CompletedData:
    reason: str
    steps: int
    mode: str
    provider: str = ""
    model: str = ""
    run_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletedData:
        steps_raw = data.get("steps")
        try:
            steps = int(steps_raw) if steps_raw is not None else 0
        except (TypeError, ValueError):
            steps = 0
        return cls(
            reason=str(data.get("reason") or "").strip(),
            steps=steps,
            mode=str(data.get("mode") or "").strip(),
            provider=str(data.get("provider") or "").strip(),
            model=str(data.get("model") or "").strip(),
            run_id=str(data.get("run_id") or "").strip(),
        )


@dataclass(frozen=True)
class ErrorData:
    error: str
    code: str = ""
    run_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ErrorData:
        return cls(
            error=str(data.get("error") or data.get("message") or "").strip(),
            code=str(data.get("code") or "").strip(),
            run_id=str(data.get("run_id") or "").strip(),
        )


@dataclass(frozen=True)
class SubagentData:
    phase: str
    agent: str = ""
    toolkits: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubagentData:
        tk = data.get("toolkits")
        toolkits = tuple(str(x) for x in tk) if isinstance(tk, list) else ()
        return cls(
            phase=str(data.get("phase") or "").strip(),
            agent=str(data.get("agent") or "").strip(),
            toolkits=toolkits,
        )


@dataclass(frozen=True)
class LlmStreamEvent:
    """Inner LLM streaming event (inside ``stream_event`` wrappers)."""

    raw: dict[str, Any]

    @property
    def type(self) -> str:
        return str(self.raw.get("type") or "")

    @property
    def is_text_delta(self) -> bool:
        return self.type == "content_block_delta"

    @property
    def is_assistant_message(self) -> bool:
        return self.type == "assistant_message"

    @property
    def text_delta(self) -> str:
        if not self.is_text_delta:
            return ""
        delta = self.raw.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta":
            return str(delta.get("text") or "")
        return ""

    @property
    def text(self) -> str:
        if self.is_text_delta:
            return self.text_delta
        if not self.is_assistant_message:
            return ""
        message = self.raw.get("message")
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "".join(parts)


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    label: str
    configured: bool
    default_model: str
    models: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ProviderInfo:
        models_raw = raw.get("models")
        models = tuple(str(m) for m in models_raw) if isinstance(models_raw, list) else ()
        return cls(
            id=str(raw.get("id") or "").strip(),
            label=str(raw.get("label") or raw.get("id") or "").strip(),
            configured=bool(raw.get("configured")),
            default_model=str(raw.get("default_model") or "").strip(),
            models=models,
        )


def answer_question_body(answers: dict[str, str]) -> dict[str, Any]:
    return {"answers": dict(answers)}


def approve_tool_body(
    *,
    approved: bool = True,
    updated_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"approved": approved}
    if updated_input is not None:
        body["updated_input"] = dict(updated_input)
    return body
