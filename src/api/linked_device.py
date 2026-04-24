"""Linked Koraku desktop app: chat may use ``execution_target=local`` only when paired."""
from __future__ import annotations

from fastapi import Request


def chat_local_execution_available(request: Request) -> bool:
    """True when a desktop agent is paired and online for this browser session or user."""
    _ = request
    # TODO: session / user pairing + presence (WebSocket from desktop, etc.)
    return False
