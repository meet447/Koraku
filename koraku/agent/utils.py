"""Formatting and working memory helpers for the Koraku agent."""
from __future__ import annotations

import json
import re
from typing import Any

from koraku.core.models import AgentMessage
from koraku.agent.budget import resolve_turn_limits

_WORKING_MEMORY_MAX_ITEMS = 8
_WORKING_MEMORY_ITEM_CHARS = 360
_WORKING_MEMORY_TOTAL_CHARS = 2_000


def build_user_message_blocks(
    user_input: str,
    image_parts: list[dict[str, str]],
) -> str | list[dict[str, Any]]:
    """Plain string when no images; otherwise Anthropic-shaped user blocks (images then text)."""
    if not image_parts:
        return user_input
    blocks: list[dict[str, Any]] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": p.get("media_type") or "image/png",
                "data": p.get("data") or "",
            },
        }
        for p in image_parts
    ]
    text = user_input.strip() or "The user attached image(s). Answer based on what you see."
    blocks.append({"type": "text", "text": text})
    return blocks


def _step_budget(user_input: str) -> tuple[str, int]:
    """Used by chat API hints; mirrors :func:`resolve_turn_limits` round cap."""
    mode, limits = resolve_turn_limits(user_input, None)
    return mode, limits.max_rounds


def _clean_one_line(text: str, max_chars: int = _WORKING_MEMORY_ITEM_CHARS) -> str:
    s = re.sub(r"\s+", " ", text or "").strip()
    if len(s) > max_chars:
        return s[: max_chars - 3].rstrip() + "..."
    return s


def _tool_result_summary(tool_result: dict[str, Any]) -> dict[str, str] | None:
    content = tool_result.get("content", "")
    tool_id = str(tool_result.get("tool_use_id") or "").strip()
    prefix = f"{tool_id}: " if tool_id else ""

    if tool_result.get("is_error"):
        return {"type": "error", "summary": prefix + _clean_one_line(str(content), 220)}
    if not isinstance(content, str) or not content.strip():
        return None

    stripped = content.strip()
    if stripped.startswith("[") and "url" in stripped:
        try:
            rows = json.loads(stripped)
        except (TypeError, ValueError):
            rows = None
        if isinstance(rows, list):
            sources: list[str] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                title = _clean_one_line(str(row.get("title") or row.get("name") or "Source"), 90)
                url = _clean_one_line(str(row.get("url") or ""), 140)
                if url:
                    sources.append(f"{title} ({url})")
                if len(sources) >= 3:
                    break
            if sources:
                return {"type": "sources", "summary": prefix + "Found sources: " + "; ".join(sources)}
        return {"type": "sources", "summary": prefix + f"Found {stripped.count('url')} source-like results."}

    if len(stripped) < 80:
        return None
    return {"type": "content", "summary": prefix + _clean_one_line(stripped)}


def format_working_memory_context(memory: list[dict[str, Any]]) -> AgentMessage | None:
    """Small per-run scratchpad shown to later loop steps, not durable memory."""
    if not memory:
        return None
    lines = [
        "## Working memory for this run",
        "Transient findings from tools. Use these to avoid re-reading, but do not treat them as durable user memory.",
    ]
    total = sum(len(line) + 1 for line in lines)
    for item in reversed(memory[-_WORKING_MEMORY_MAX_ITEMS:]):
        kind = _clean_one_line(str(item.get("type") or "note"), 40)
        summary = _clean_one_line(str(item.get("summary") or ""))
        line = f"- {kind}: {summary}"
        if total + len(line) + 1 > _WORKING_MEMORY_TOTAL_CHARS:
            lines.append("- note: Additional findings omitted to keep context small.")
            break
        lines.append(line)
        total += len(line) + 1
    return AgentMessage(role="user", content="\n".join(lines))


def update_working_memory(memory: list[dict[str, Any]], tool_results: list[dict[str, Any]]) -> None:
    for tr in tool_results:
        summary = _tool_result_summary(tr)
        if summary is not None:
            memory.append(summary)
    if len(memory) > _WORKING_MEMORY_MAX_ITEMS * 2:
        del memory[:-_WORKING_MEMORY_MAX_ITEMS * 2]
