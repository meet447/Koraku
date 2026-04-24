"""Per-turn workspace root for agent tools (defaults to process workspace)."""
from __future__ import annotations

import os
from contextvars import ContextVar, Token
from typing import Iterator

from contextlib import contextmanager

_agent_workspace_root: ContextVar[str | None] = ContextVar("koraku_agent_workspace_root", default=None)


def effective_workspace_dir() -> str:
    """Workspace for the current agent turn: override when set, else ``workspace_dir()``."""
    override = _agent_workspace_root.get()
    if override is not None:
        return override
    from src.workspace.paths import workspace_dir

    return workspace_dir()


@contextmanager
def agent_workspace_scope(root: str) -> Iterator[None]:
    """Bind ``root`` as the active workspace for the duration of the context."""
    token: Token[str | None] = _agent_workspace_root.set(os.path.abspath(root))
    try:
        yield
    finally:
        _agent_workspace_root.reset(token)
