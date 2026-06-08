"""Context for **Task** so subagent handlers reach the parent agent during a turn."""
from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

from koraku.agent.agent_definition import AgentDefinition

if TYPE_CHECKING:
    from koraku.agent.runtime_context import AgentRunContext
    from koraku.core.models import SessionState


@dataclass(frozen=True)
class TaskDelegateContext:
    agent: Any
    emit: Callable[[dict[str, Any]], None]
    session: SessionState
    workspace: str
    model: str | None
    provider: str | None
    client_timezone: str | None
    client_locale: str | None
    execution_target: str
    blaxel_sandbox_active: bool
    run_context: AgentRunContext | None
    cloud_sandbox: Any
    account_personalization: dict[str, str] | None
    run_id: str | None
    cancel_event: Any
    agents: dict[str, AgentDefinition] = field(default_factory=dict)
    depth: int = 0


_ctx: ContextVar[TaskDelegateContext | None] = ContextVar("koraku_task_delegate_ctx", default=None)


def set_task_delegate_context(ctx: TaskDelegateContext) -> Token:
    return _ctx.set(ctx)


def reset_task_delegate_context(token: Token | None) -> None:
    if token is not None:
        _ctx.reset(token)


def get_task_delegate_context() -> TaskDelegateContext | None:
    return _ctx.get()
