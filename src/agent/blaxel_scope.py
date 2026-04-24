"""ContextVar binding the active Blaxel ``SandboxInstance`` for tool handlers."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Iterator

_active_blaxel_sandbox: ContextVar[Any | None] = ContextVar("koraku_blaxel_sandbox", default=None)


def get_active_blaxel_sandbox() -> Any | None:
    return _active_blaxel_sandbox.get()


@contextmanager
def blaxel_sandbox_scope(sandbox: Any | None) -> Iterator[None]:
    if sandbox is None:
        yield
        return
    token: Token[Any | None] = _active_blaxel_sandbox.set(sandbox)
    try:
        yield
    finally:
        _active_blaxel_sandbox.reset(token)
