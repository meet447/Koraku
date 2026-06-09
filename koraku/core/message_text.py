"""Extract plain text from agent message content blocks."""
from __future__ import annotations

from typing import Any


def message_text(content: str | list[dict[str, Any]]) -> str:
    """Extract plain text from an agent message ``content`` field."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
        elif block.get("type") == "tool_result":
            parts.append(str(block.get("content") or ""))
    return "".join(parts).strip()
