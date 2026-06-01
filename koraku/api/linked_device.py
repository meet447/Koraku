"""Linked Koraku desktop app: chat may use ``execution_target=local`` only when paired."""
from __future__ import annotations

from fastapi import Request


def chat_local_execution_available(request: Request) -> bool:
    return getattr(request.state, "is_local_execution", False)
