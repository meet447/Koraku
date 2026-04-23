"""Context management for long-running agent conversations.

Manages token budget by:
- Summarizing old conversation turns
- Dropping thinking tokens from history
- Truncating long tool results
- Maintaining a sliding window
"""
import json
from typing import Any

from src.core.config import settings
from src.core.models import AgentMessage


class ContextManager:
    """Manages conversation context within a token budget."""

    def __init__(
        self,
        max_messages: int = 20,
        summarize_after: int = 12,
        max_tool_result_chars: int = 2000,
    ):
        self.max_messages = max_messages
        self.summarize_after = summarize_after
        self.max_tool_result_chars = max_tool_result_chars
        self.summaries: list[str] = []

    def process_messages(self, messages: list[AgentMessage]) -> list[AgentMessage]:
        """
        Process messages for LLM consumption:
        1. Drop thinking tokens
        2. Truncate long tool results
        3. Summarize old history if too long
        4. Apply sliding window
        """
        cleaned = self._drop_thinking(messages)
        cleaned = self._truncate_tool_results(cleaned)
        cleaned = self._summarize_if_needed(cleaned)
        cleaned = self._apply_sliding_window(cleaned)
        return cleaned

    def _drop_thinking(self, messages: list[AgentMessage]) -> list[AgentMessage]:
        """Remove thinking blocks from assistant messages to save tokens."""
        result = []
        for msg in messages:
            if isinstance(msg.content, str):
                result.append(msg)
                continue
            # Filter out thinking blocks, keep only text and tool_use/tool_result
            filtered = []
            for block in msg.content:
                if isinstance(block, dict):
                    if block.get("type") == "thinking":
                        continue
                    filtered.append(block)
                else:
                    filtered.append(block)
            result.append(AgentMessage(role=msg.role, content=filtered))
        return result

    def _truncate_tool_results(self, messages: list[AgentMessage]) -> list[AgentMessage]:
        """Truncate long tool results to save tokens."""
        result = []
        for msg in messages:
            if isinstance(msg.content, str):
                result.append(msg)
                continue
            filtered = []
            for block in msg.content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if isinstance(content, str) and len(content) > self.max_tool_result_chars:
                        truncated = (
                            content[: self.max_tool_result_chars]
                            + f"\n...[truncated: tool result exceeded {self.max_tool_result_chars} chars for LLM context]"
                        )
                        new_block = dict(block)
                        new_block["content"] = truncated
                        filtered.append(new_block)
                    else:
                        filtered.append(block)
                else:
                    filtered.append(block)
            result.append(AgentMessage(role=msg.role, content=filtered))
        return result

    def _summarize_if_needed(self, messages: list[AgentMessage]) -> list[AgentMessage]:
        """If conversation is very long, summarize the oldest turns."""
        if len(messages) <= self.summarize_after:
            return messages

        # Keep the first user message, summarize everything between
        # first message and the last N messages
        keep_recent = 8
        to_summarize = messages[1:-keep_recent]

        if not to_summarize:
            return messages

        # Build a simple summary
        summary_parts = []
        search_count = 0
        fetch_count = 0
        file_count = 0
        key_findings = []

        for msg in to_summarize:
            if msg.role == "assistant" and isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use":
                            name = block.get("name", "")
                            if "Search" in name or "search" in name:
                                search_count += 1
                            elif name in ("WebPage", "WebFetch", "Firecrawl", "Fetch"):
                                fetch_count += 1
                            elif name in ("Read", "Glob", "Grep"):
                                file_count += 1
            elif msg.role == "user" and isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        content = block.get("content", "")
                        if isinstance(content, str):
                            # Extract URLs or key data
                            if content.startswith("[") and "url" in content:
                                try:
                                    data = json.loads(content)
                                    for item in data[:3]:
                                        if isinstance(item, dict) and item.get("url"):
                                            key_findings.append(f"- {item.get('title', 'Source')}: {item['url']}")
                                except Exception:
                                    pass
                            elif len(content) > 100 and not content.startswith("Error"):
                                key_findings.append(f"- {content[:120]}...")

        summary_lines = ["## Previous Research Summary"]
        if search_count:
            summary_lines.append(f"- Performed {search_count} searches")
        if fetch_count:
            summary_lines.append(f"- Fetched {fetch_count} pages")
        if file_count:
            summary_lines.append(f"- Examined {file_count} files")
        if key_findings:
            summary_lines.append("- Key sources/findings:")
            for f in key_findings[:5]:
                summary_lines.append(f"  {f}")

        summary_text = "\n".join(summary_lines)

        # Rebuild message list: first msg + summary + recent msgs
        new_messages = [messages[0]]
        new_messages.append(AgentMessage(role="user", content=summary_text))
        new_messages.extend(messages[-keep_recent:])
        return new_messages

    def _apply_sliding_window(self, messages: list[AgentMessage]) -> list[AgentMessage]:
        """Keep only the most recent messages within the window."""
        if len(messages) <= self.max_messages:
            return messages
        # Always keep the first message (original user query)
        # and the most recent N-1 messages
        return [messages[0]] + messages[-(self.max_messages - 1):]

    def estimate_tokens(self, messages: list[AgentMessage]) -> int:
        """Rough token estimate (4 chars ~ 1 token for English)."""
        total_chars = 0
        for msg in messages:
            if isinstance(msg.content, str):
                total_chars += len(msg.content)
            else:
                total_chars += len(json.dumps(msg.content))
        return total_chars // 4
