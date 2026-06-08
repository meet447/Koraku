"""Per-run context for tools and the tool executor (emit, hooks, permission mode)."""
from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

from koraku.agent.hooks import AgentHooks
from koraku.agent.permissions import PermissionMode, normalize_permission_mode

_active_emit: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar(
    "koraku_active_emit",
    default=None,
)
_active_run_id: ContextVar[str | None] = ContextVar("koraku_active_run_id", default=None)
_active_session_id: ContextVar[str | None] = ContextVar("koraku_active_session_id", default=None)
_active_permission_mode: ContextVar[PermissionMode] = ContextVar(
    "koraku_active_permission_mode",
    default="default",
)
_active_hooks: ContextVar[AgentHooks | None] = ContextVar("koraku_active_hooks", default=None)
_active_ask_user_timeout: ContextVar[float] = ContextVar(
    "koraku_active_ask_user_timeout",
    default=600.0,
)


@dataclass
class ActiveRunBindings:
    emit: Callable[[dict[str, Any]], None] | None = None
    run_id: str | None = None
    session_id: str | None = None
    permission_mode: PermissionMode = "default"
    hooks: AgentHooks | None = None
    ask_user_timeout_seconds: float = 600.0


def bind_active_run(bindings: ActiveRunBindings) -> list[Token[Any]]:
    tokens: list[Token[Any]] = []
    tokens.append(_active_emit.set(bindings.emit))
    tokens.append(_active_run_id.set(bindings.run_id))
    tokens.append(_active_session_id.set(bindings.session_id))
    tokens.append(_active_permission_mode.set(normalize_permission_mode(bindings.permission_mode)))
    tokens.append(_active_hooks.set(bindings.hooks))
    tokens.append(_active_ask_user_timeout.set(float(bindings.ask_user_timeout_seconds)))
    return tokens


def reset_active_run(tokens: list[Token[Any]]) -> None:
    for tok in reversed(tokens):
        var = tok.var  # type: ignore[attr-defined]
        var.reset(tok)


def get_active_emit() -> Callable[[dict[str, Any]], None] | None:
    return _active_emit.get()


def get_active_run_id() -> str | None:
    return _active_run_id.get()


def get_active_session_id() -> str | None:
    return _active_session_id.get()


def get_active_permission_mode() -> PermissionMode:
    return _active_permission_mode.get()


def get_active_hooks() -> AgentHooks | None:
    return _active_hooks.get()


def get_active_ask_user_timeout() -> float:
    return _active_ask_user_timeout.get()
