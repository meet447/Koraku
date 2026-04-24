"""Unified LLM client with compact prompts for small models.

Providers:
- anthropic: native Messages API + tools
- fireworks / custom_openai: OpenAI-compatible ``POST /v1/chat/completions`` (streaming SSE).

Prism Bonsai (e.g. ``CUSTOM_BASE_URL=https://prism-ml-bonsai-demo.hf.space/v1``) uses the same
OpenAI-compatible path; model IDs such as ``Bonsai-8B-Q1_0`` and ``Ternary-Bonsai-8B-Q2_0``
come from ``GET /v1/models`` on that host. Fireworks uses the same ``/v1/models`` + Bearer key.
"""
import asyncio
import json
import re
from typing import Any, AsyncIterator, Iterator

import httpx
from anthropic import APIStatusError, AsyncAnthropic

from src.core.config import settings
from src.core.models import AgentMessage
from src.llm.thinking_parse import THINKING_BLOCK_INSTRUCTION, StreamKind, TaggedStreamParser
from src.llm.sanitize import VisibleToolJsonFilter

# OpenAI-compatible default when no CUSTOM_BASE_URL (Prism Bonsai public Space)
BONSAI_PUBLIC_API_BASE = "https://prism-ml-bonsai-demo.hf.space/v1"


def _retryable_http_status(status_code: int) -> bool:
    return status_code in (408, 409, 425, 429, 500, 502, 503, 504)


def _openai_delta_content_to_str(raw: Any) -> str:
    """Coerce ``choices[].delta.content`` to plain text (OpenAI string or list-of-parts shapes)."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts: list[str] = []
        for p in raw:
            if isinstance(p, dict):
                if p.get("type") == "text" and isinstance(p.get("text"), str):
                    parts.append(p["text"])
                elif isinstance(p.get("content"), str):
                    parts.append(p["content"])
            elif isinstance(p, str):
                parts.append(p)
        return "".join(parts)
    return str(raw)


def _accumulate_openai_tool_call_deltas(
    slots: dict[int, dict[str, str]],
    tool_calls_delta: list[Any],
) -> None:
    """Merge streaming ``choices[].delta.tool_calls`` fragments (OpenAI / Fireworks / Kimi)."""
    for tc in tool_calls_delta:
        if not isinstance(tc, dict):
            continue
        idx = int(tc.get("index", 0))
        slot = slots.setdefault(idx, {"id": "", "name": "", "arguments": ""})
        tid = tc.get("id")
        if tid:
            slot["id"] = str(tid)
        fn = tc.get("function")
        if isinstance(fn, dict):
            if fn.get("name"):
                slot["name"] = str(fn["name"])
            arg = fn.get("arguments")
            if arg is not None and arg != "":
                slot["arguments"] += str(arg)


def _tool_call_slots_to_blocks(slots: dict[int, dict[str, str]]) -> list[dict[str, Any]]:
    """Turn accumulated native tool-call slots into Anthropic-style ``tool_use`` blocks."""
    blocks: list[dict[str, Any]] = []
    for idx in sorted(slots.keys()):
        slot = slots[idx]
        name = (slot.get("name") or "").strip()
        raw_args = slot.get("arguments") or ""
        tid = (slot.get("id") or "").strip() or f"tool_{idx}"
        if not name:
            continue
        try:
            inp = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            inp = {"_partial_json": raw_args}
        if not isinstance(inp, dict):
            inp = {"_value": inp}
        blocks.append({"type": "tool_use", "id": tid, "name": name, "input": inp})
    return blocks


def _anthropic_tool_definitions(tool_schemas: list[Any]) -> list[dict[str, Any]]:
    """Anthropic Messages API requires JSON tool defs, not Python Tool objects."""
    out: list[dict[str, Any]] = []
    for t in tool_schemas or []:
        if hasattr(t, "to_anthropic_schema"):
            out.append(t.to_anthropic_schema())
        elif isinstance(t, dict) and "name" in t and "input_schema" in t:
            out.append(t)
    return out


class UnifiedLLMClient:
    """Routes to Anthropic or OpenAI-compatible backends."""

    def __init__(self, provider_override: str | None = None, *, custom_base_url: str | None = None) -> None:
        self.provider = (provider_override or settings.llm_provider or "custom_openai").strip().lower()
        if self.provider == "anthropic":
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.model = settings.anthropic_model
        elif self.provider == "fireworks":
            self.model = settings.fireworks_model
            self.base_url = settings.fireworks_base_url.rstrip("/")
            self.api_key = settings.fireworks_api_key
            self.timeout = 120.0
        elif self.provider == "custom_openai":
            cm = (settings.custom_model or "").strip()
            self.model = cm or "Ternary-Bonsai-8B-Q2_0"
            resolved = (custom_base_url or settings.custom_base_url or "").strip().rstrip("/")
            self.base_url = resolved or BONSAI_PUBLIC_API_BASE.rstrip("/")
            self.api_key = (settings.custom_api_key or "").strip()
            self.timeout = 120.0
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def build_compact_tool_prompt(self, tools: list[Any]) -> str:
        """Ultra-compact tool prompt for small models."""
        lines = [
            "",
            "TOOLS: Emit exactly one JSON object per call (double quotes, colons — not Ruby ``=>``):",
            "{\"tool\":\"Name\",\"parameters\":{...}}",
            "Do not use [TOOL_CALL] tags or ``tool =>`` syntax.",
            "",
        ]
        for tool in tools:
            if hasattr(tool, "to_compact_prompt"):
                lines.append(tool.to_compact_prompt())
            else:
                # Fallback for raw schema dicts
                name = tool.get("name", "Unknown")
                desc = tool.get("description", "")
                lines.append(f"{name}: {desc}")
            lines.append("")
        lines.append("Call tools when needed. Provide final answer when done.")
        return "\n".join(lines)

    def _openai_user_multimodal_parts(self, blocks: list[Any]) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        for block in blocks:
            if not isinstance(block, dict):
                parts.append({"type": "text", "text": str(block)})
                continue
            t = block.get("type")
            if t == "image":
                src = block.get("source") or {}
                if src.get("type") == "base64" and src.get("data"):
                    mt = str(src.get("media_type") or "image/png")
                    b64 = str(src.get("data", ""))
                    parts.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64,{b64}"}})
            elif t == "text":
                parts.append({"type": "text", "text": str(block.get("text", ""))})
            elif t == "tool_result":
                tid = block.get("tool_use_id", "?")
                content = block.get("content", "")
                parts.append({"type": "text", "text": f"[Result {tid}]:\n{content}"})
            elif t == "tool_use":
                parts.append({
                    "type": "text",
                    "text": f"[Call {block.get('name', '?')}]:\n{json.dumps(block.get('input', {}))}",
                })
            else:
                parts.append({"type": "text", "text": json.dumps(block)})
        return parts

    def _user_blocks_have_image(self, blocks: list[Any]) -> bool:
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "image":
                return True
        return False

    def _convert_messages_openai(self, messages: list[AgentMessage]) -> list[dict[str, Any]]:
        openai_msgs: list[dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg.content, str):
                openai_msgs.append({"role": msg.role, "content": msg.content})
            elif msg.role == "user" and self._user_blocks_have_image(msg.content):
                openai_msgs.append({
                    "role": "user",
                    "content": self._openai_user_multimodal_parts(msg.content),
                })
            else:
                parts: list[str] = []
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            parts.append(f"[Result {block.get('tool_use_id', '?')}]:\n{block.get('content', '')}")
                        elif block.get("type") == "tool_use":
                            parts.append(f"[Call {block.get('name', '?')}]:\n{json.dumps(block.get('input', {}))}")
                        elif block.get("type") == "text":
                            parts.append(block.get("text", ""))
                        else:
                            parts.append(json.dumps(block))
                    else:
                        parts.append(str(block))
                openai_msgs.append({"role": msg.role, "content": "\n".join(parts)})
        return openai_msgs

    def _strip_markdown(self, text: str) -> str:
        """Strip markdown code blocks that some models wrap JSON in."""
        # Remove ```json ... ``` blocks, keeping only the inner JSON
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        return text

    def _normalize_ruby_style_tool_json(self, blob: str) -> str:
        """MiniMax / some Fireworks models emit ``{tool => \"X\", parameters => {...}}`` instead of JSON."""
        t = blob.strip()
        t = re.sub(r"\[TOOL_CALL\]\s*", "", t, flags=re.IGNORECASE)
        # Strip closing tag; model may truncate before ``]`` (stream cut-off).
        t = re.split(r"\[/TOOL_CALL", t, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        t = re.sub(r"{\s*tool\s*=>", '{"tool":', t)
        t = re.sub(r",\s*parameters\s*=>", ', "parameters":', t)
        return t.strip()

    def _parse_tool_calls(self, text: str) -> list[dict[str, Any]]:
        """Extract tool calls from text. Handles multiple formats."""
        blocks: list[dict[str, Any]] = []
        tool_calls = []

        # Strip markdown code blocks first
        clean_text = self._strip_markdown(text)

        # Format 0: [TOOL_CALL] + Ruby-style hash (MiniMax on Fireworks)
        for m in re.finditer(
            r"\[TOOL_CALL\]\s*(\{[\s\S]*?\})\s*\[/TOOL_CALL\]",
            clean_text,
            re.IGNORECASE,
        ):
            raw_blob = m.group(1)
            normalized = self._normalize_ruby_style_tool_json(raw_blob)
            try:
                parsed = json.loads(normalized)
                if isinstance(parsed, dict) and isinstance(parsed.get("tool"), str):
                    tool_calls.append({"start": m.start(), "end": m.end(), "data": parsed})
            except json.JSONDecodeError:
                pass
        if not tool_calls and ("tool" in clean_text.lower() and "=>" in clean_text):
            normalized = self._normalize_ruby_style_tool_json(clean_text)
            try:
                parsed = json.loads(normalized)
                if isinstance(parsed, dict) and isinstance(parsed.get("tool"), str):
                    tool_calls.append({"start": 0, "end": len(clean_text), "data": parsed})
            except json.JSONDecodeError:
                pass

        # Format 1: {"tool": "Name", "parameters": {...}}
        for pattern in [
            r'\{[^{}]*"tool"[^{}]*\}',
            r'\{(?:[^{}]|\{[^{}]*\})*"tool"(?:[^{}]|\{[^{}]*\})*\}',
        ]:
            for match in re.finditer(pattern, clean_text, re.DOTALL if "(?:" in pattern else 0):
                try:
                    parsed = json.loads(match.group(0))
                    if "tool" in parsed and isinstance(parsed["tool"], str):
                        inside = any(t["start"] <= match.start() < t["end"] for t in tool_calls)
                        if not inside:
                            tool_calls.append({"start": match.start(), "end": match.end(), "data": parsed})
                except json.JSONDecodeError:
                    pass

        # Format 2: [Call Name]:\n{"param": "value"} (some models use this)
        for match in re.finditer(r'\[Call\s+([A-Za-z]+)\]\s*:\s*(\{[^{}]*\})', clean_text):
            try:
                tool_name = match.group(1)
                params = json.loads(match.group(2))
                already = any(t["start"] == match.start() for t in tool_calls)
                if not already:
                    tool_calls.append({
                        "start": match.start(),
                        "end": match.end(),
                        "data": {"tool": tool_name, "parameters": params},
                    })
            except (json.JSONDecodeError, IndexError):
                pass

        if not tool_calls:
            if text.strip():
                blocks.append({"type": "text", "text": text})
            return blocks

        tool_calls.sort(key=lambda x: x["start"])
        last_end = 0
        for i, tc in enumerate(tool_calls):
            before = clean_text[last_end:tc["start"]]
            if before.strip():
                blocks.append({"type": "text", "text": before.strip()})
            params = tc["data"].get("parameters", tc["data"].get("input", tc["data"].get("args", {})))
            blocks.append({
                "type": "tool_use",
                "id": f"tool_{i}",
                "name": tc["data"]["tool"],
                "input": params if isinstance(params, dict) else {},
            })
            last_end = tc["end"]

        after = clean_text[last_end:]
        if after.strip():
            blocks.append({"type": "text", "text": after.strip()})
        return blocks

    async def stream(
        self,
        messages: list[AgentMessage],
        tool_schemas: list[Any],
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        model_id = (model or "").strip() or self.model
        if self.provider == "anthropic":
            async for ev in self._stream_anthropic(messages, tool_schemas, system_prompt, model_id=model_id):
                yield ev
        else:
            async for ev in self._stream_openai(messages, tool_schemas, system_prompt, model_id=model_id):
                yield ev

    async def _stream_anthropic(
        self,
        messages: list[AgentMessage],
        tool_schemas: list[Any],
        system_prompt: str | None = None,
        *,
        model_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        anthropic_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": settings.max_tokens,
            "messages": anthropic_messages,
            "stream": True,
        }
        tools = _anthropic_tool_definitions(tool_schemas)
        if tools:
            kwargs["tools"] = tools
        if system_prompt:
            kwargs["system"] = system_prompt

        attempts = settings.llm_max_retries + 1
        last_error: str | None = None
        for attempt in range(attempts):
            try:
                async with self._client.messages.stream(**kwargs) as stream:
                    assistant_content: list[dict[str, Any]] = []
                    current_block_type = None
                    current_json = ""

                    async for event in stream:
                        if event.type == "message_start":
                            yield {"type": "message_start", "message": {
                                "id": event.message.id, "model": event.message.model,
                                "role": event.message.role, "content": [],
                                "stop_reason": None,
                                "usage": {"input_tokens": event.message.usage.input_tokens, "output_tokens": event.message.usage.output_tokens},
                            }}

                        elif event.type == "content_block_start":
                            current_block_type = event.content_block.type
                            block = {"type": event.content_block.type}
                            if event.content_block.type == "thinking":
                                block["thinking"] = ""
                                block["signature"] = ""
                            elif event.content_block.type == "tool_use":
                                block["id"] = event.content_block.id
                                block["name"] = event.content_block.name
                                block["input"] = {}
                            elif event.content_block.type == "text":
                                block["text"] = ""
                            assistant_content.append(block)
                            yield {"type": "content_block_start", "index": event.index, "content_block": block}

                        elif event.type == "content_block_delta":
                            delta: dict[str, Any] = {"type": event.delta.type}
                            if event.delta.type == "thinking_delta":
                                delta["thinking"] = event.delta.thinking
                            elif event.delta.type == "signature_delta":
                                delta["signature"] = event.delta.signature
                            elif event.delta.type == "text_delta":
                                delta["text"] = event.delta.text
                            elif event.delta.type == "input_json_delta":
                                delta["partial_json"] = event.delta.partial_json
                                current_json += event.delta.partial_json
                            yield {"type": "content_block_delta", "index": event.index, "delta": delta}

                        elif event.type == "content_block_stop":
                            if current_block_type == "tool_use" and current_json:
                                try:
                                    parsed = json.loads(current_json)
                                    if assistant_content and assistant_content[-1]["type"] == "tool_use":
                                        assistant_content[-1]["input"] = parsed
                                except json.JSONDecodeError:
                                    pass
                            yield {"type": "content_block_stop", "index": event.index}
                            current_block_type = None
                            current_json = ""

                        elif event.type == "message_delta":
                            delta = {}
                            if event.delta.stop_reason:
                                delta["stop_reason"] = event.delta.stop_reason
                            usage = {}
                            if event.usage:
                                usage = {"input_tokens": event.usage.input_tokens, "output_tokens": event.usage.output_tokens}
                            yield {"type": "message_delta", "delta": delta, "usage": usage}

                        elif event.type == "message_stop":
                            yield {"type": "message_stop", "message": {}}

                    final = await stream.get_final_message()
                    assembled = {
                        "id": final.id, "model": final.model, "role": final.role,
                        "content": [], "stop_reason": final.stop_reason,
                        "usage": {"input_tokens": final.usage.input_tokens, "output_tokens": final.usage.output_tokens},
                    }
                    for block in final.content:
                        if block.type == "text":
                            assembled["content"].append({"type": "text", "text": block.text})
                        elif block.type == "thinking":
                            assembled["content"].append({"type": "thinking", "thinking": block.thinking, "signature": block.signature})
                        elif block.type == "tool_use":
                            assembled["content"].append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
                    yield {"type": "assistant_message", "message": assembled}
                return
            except APIStatusError as e:
                last_error = f"{e.status_code}: {e!s}"
                if _retryable_http_status(e.status_code) and attempt < attempts - 1:
                    delay = settings.llm_retry_base_seconds * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                yield {"type": "message_stop", "message": {}}
                yield {"type": "assistant_message", "message": {
                    "content": [{"type": "text", "text": f"LLM request failed: {last_error}"}],
                    "stop_reason": "end_turn",
                    "usage": {},
                }}
                return
            except Exception as e:
                yield {"type": "message_stop", "message": {}}
                yield {"type": "assistant_message", "message": {
                    "content": [{"type": "text", "text": f"LLM request failed: {e}"}],
                    "stop_reason": "end_turn",
                    "usage": {},
                }}
                return

    async def _stream_openai(
        self,
        messages: list[AgentMessage],
        tool_schemas: list[Any],
        system_prompt: str | None = None,
        *,
        model_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        # Use COMPACT tool prompt instead of native tool schemas
        # Only append tool guidance when tools are actually provided
        if tool_schemas:
            tool_prompt = self.build_compact_tool_prompt(tool_schemas)
            full_system = (system_prompt or "") + tool_prompt + THINKING_BLOCK_INSTRUCTION
        else:
            full_system = (system_prompt or "") + THINKING_BLOCK_INSTRUCTION

        openai_messages = []
        if full_system:
            openai_messages.append({"role": "system", "content": full_system})
        openai_messages.extend(self._convert_messages_openai(messages))

        payload = {
            "model": model_id,
            "messages": openai_messages,
            "stream": True,
            "max_tokens": settings.max_tokens,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "top_k": settings.top_k,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": settings.user_agent,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp: httpx.Response | None = None
            err_text = ""
            attempts = settings.llm_max_retries + 1
            for attempt in range(attempts):
                try:
                    r = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                except httpx.RequestError as e:
                    err_text = str(e)
                    if attempt < attempts - 1:
                        await asyncio.sleep(settings.llm_retry_base_seconds * (2**attempt))
                        continue
                    yield {"type": "message_stop", "message": {}}
                    yield {"type": "assistant_message", "message": {
                        "content": [{"type": "text", "text": f"Connection error after {attempts} attempts: {err_text}"}],
                    }}
                    return
                if r.status_code < 400:
                    resp = r
                    break
                err_text = r.text[:800]
                if _retryable_http_status(r.status_code) and attempt < attempts - 1:
                    await asyncio.sleep(settings.llm_retry_base_seconds * (2**attempt))
                    continue
                yield {"type": "message_stop", "message": {}}
                yield {"type": "assistant_message", "message": {
                    "content": [{"type": "text", "text": f"API error {r.status_code}: {err_text}"}],
                }}
                return

            if resp is None:
                yield {"type": "message_stop", "message": {}}
                yield {"type": "assistant_message", "message": {
                    "content": [{"type": "text", "text": f"API request failed after {attempts} attempts: {err_text}"}],
                }}
                return

            async for event in self._process_openai_stream(resp, model_id):
                yield event

    async def _process_openai_stream(
        self,
        resp: httpx.Response,
        model_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        accumulated_text = ""
        reasoning_accumulated = ""
        message_id = ""
        think_parser = TaggedStreamParser()
        visible_tool_filter = VisibleToolJsonFilter()
        native_tool_slots: dict[int, dict[str, str]] = {}
        reasoning_block_open = False
        # Kimi / Fireworks often put scratch reasoning in ``reasoning_content`` instead of
        # ``<koraku_thinking>`` tags. Tag path uses ``thinking_emitted`` for text index; this
        # flag keeps native-reasoning streams from reusing block index 0 for answer text.
        native_reasoning_emitted = False

        yield {"type": "message_start", "message": {
            "id": "", "model": model_id, "role": "assistant",
            "content": [], "stop_reason": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }}

        def emit_tagged_stream_items(
            items: list[tuple[StreamKind, str]],
        ) -> Iterator[dict[str, Any]]:
            nonlocal accumulated_text, reasoning_block_open

            def text_block_index() -> int:
                return 1 if (think_parser.thinking_emitted or native_reasoning_emitted) else 0

            for kind, payload in items:
                if kind == "thinking_block_start":
                    yield {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": {"type": "thinking", "thinking": "", "signature": ""},
                    }
                elif kind == "thinking_delta":
                    yield {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "thinking_delta", "thinking": payload},
                    }
                elif kind == "thinking_block_stop":
                    yield {"type": "content_block_stop", "index": 0}
                elif kind == "text_block_start":
                    if reasoning_block_open:
                        yield {"type": "content_block_stop", "index": 0}
                        reasoning_block_open = False
                    tidx = text_block_index()
                    yield {
                        "type": "content_block_start",
                        "index": tidx,
                        "content_block": {"type": "text", "text": ""},
                    }
                elif kind == "text_delta":
                    if reasoning_block_open:
                        yield {"type": "content_block_stop", "index": 0}
                        reasoning_block_open = False
                    tidx = text_block_index()
                    accumulated_text += payload
                    for safe in visible_tool_filter.feed(payload):
                        if not safe:
                            continue
                        yield {
                            "type": "content_block_delta",
                            "index": tidx,
                            "delta": {"type": "text_delta", "text": safe},
                        }

        buffer = ""
        async for chunk in resp.aiter_text():
            buffer += chunk
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = parsed.get("choices")
                if not isinstance(choices, list) or len(choices) == 0:
                    continue
                choice0 = choices[0] if isinstance(choices[0], dict) else {}
                delta = choice0.get("delta")
                if not isinstance(delta, dict):
                    delta = {}
                msg_obj = choice0.get("message")
                if isinstance(msg_obj, dict):
                    mtc = msg_obj.get("tool_calls")
                    if isinstance(mtc, list) and mtc:
                        _accumulate_openai_tool_call_deltas(native_tool_slots, mtc)

                raw_tcs = delta.get("tool_calls")
                if isinstance(raw_tcs, list) and raw_tcs:
                    _accumulate_openai_tool_call_deltas(native_tool_slots, raw_tcs)

                reasoning = delta.get("reasoning_content")
                if isinstance(reasoning, str) and reasoning:
                    reasoning_accumulated += reasoning
                    if not reasoning_block_open:
                        native_reasoning_emitted = True
                        yield {"type": "content_block_start", "index": 0, "content_block": {
                            "type": "thinking", "thinking": "", "signature": "",
                        }}
                        reasoning_block_open = True
                    yield {"type": "content_block_delta", "index": 0, "delta": {
                        "type": "thinking_delta", "thinking": reasoning,
                    }}

                content = _openai_delta_content_to_str(delta.get("content"))
                if not content.strip() and isinstance(delta.get("text"), str) and delta["text"].strip():
                    content = delta["text"]
                if not message_id and parsed.get("id"):
                    message_id = parsed["id"]
                if content:
                    for ev in emit_tagged_stream_items(think_parser.feed(content)):
                        yield ev

        for ev in emit_tagged_stream_items(think_parser.flush_eof()):
            yield ev

        tidx_flush = 1 if (think_parser.thinking_emitted or native_reasoning_emitted) else 0
        for tail in visible_tool_filter.flush():
            if not tail:
                continue
            yield {
                "type": "content_block_delta",
                "index": tidx_flush,
                "delta": {"type": "text_delta", "text": tail},
            }

        if think_parser.text_block_started:
            yield {"type": "content_block_stop", "index": tidx_flush}
        if reasoning_block_open:
            yield {"type": "content_block_stop", "index": 0}

        native_blocks = _tool_call_slots_to_blocks(native_tool_slots)
        compact_blocks = self._parse_tool_calls(accumulated_text)

        if native_blocks:
            text_parts = [b for b in compact_blocks if b.get("type") == "text"]
            content_blocks = text_parts + native_blocks
        else:
            content_blocks = compact_blocks

        if not content_blocks:
            # Kimi / some Fireworks models stream scratch + answer in ``reasoning_content`` only;
            # that path updates SSE thinking but never ``accumulated_text``, so compact_blocks is empty.
            if reasoning_accumulated.strip():
                content_blocks = [{"type": "text", "text": reasoning_accumulated.strip()}]
            else:
                content_blocks = [{
                    "type": "text",
                    "text": (
                        "The model returned an empty completion (no text and no parsed tool calls). "
                        "If you were expecting tools, the upstream stream may use a format this client "
                        "does not yet map — try again or switch model/provider."
                    ),
                }]

        stop_reason = "tool_use" if any(b.get("type") == "tool_use" for b in content_blocks) else "end_turn"

        yield {"type": "message_delta", "delta": {"stop_reason": stop_reason}, "usage": {}}
        yield {"type": "message_stop", "message": {}}
        yield {"type": "assistant_message", "message": {
            "id": message_id or "unknown", "model": model_id, "role": "assistant",
            "content": content_blocks, "stop_reason": stop_reason, "usage": {},
        }}
