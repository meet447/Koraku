"""Bud-shaped SSE payloads with Koraku-branded outer types: ``koraku.*`` and stringified ``koraku.event`` bodies."""
from __future__ import annotations

import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.tools.registry import AVAILABLE_TOOLS


def _now_ms() -> int:
    return int(time.time() * 1000)


def new_pty_session_id() -> str:
    return f"koraku-{_now_ms()}-{secrets.token_hex(3)}"


def new_inner_session_id() -> str:
    return secrets.token_hex(12)


def _koraku_envelope_event(inner: dict[str, Any]) -> dict[str, Any]:
    return {"type": "koraku.event", "data": json.dumps(inner, ensure_ascii=False)}


def route_decision_data(provider_id: str, model: str) -> dict[str, Any]:
    pid = (provider_id or "").strip().lower()
    if pid == "anthropic":
        return {"runtime": "claude", "model": model, "meta": {"isByok": False, "provider": "anthropic"}}
    if pid == "fireworks":
        return {"runtime": "fireworks", "model": model, "meta": {"isByok": False, "provider": "fireworks"}}
    if pid == "bonsai":
        return {"runtime": "custom_openai", "model": model, "meta": {"isByok": False, "provider": "bonsai"}}
    return {"runtime": "custom_openai", "model": model, "meta": {"isByok": False, "provider": "openai_compat"}}


def build_system_init_inner(
    *,
    cwd: str,
    inner_session_id: str,
    model: str,
    koraku: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tools = [t.to_anthropic_schema() for t in AVAILABLE_TOOLS]
    body: dict[str, Any] = {
        "type": "system",
        "subtype": "init",
        "cwd": cwd,
        "session_id": inner_session_id,
        "tools": tools,
        "mcp_servers": [],
        "model": model,
        "permissionMode": "default",
        "slash_commands": [],
        "apiKeySource": "koraku",
        "output_style": "default",
        "uuid": str(uuid.uuid4()),
    }
    if koraku:
        body["koraku"] = koraku
    return body


def _wrap_stream_event(
    raw_event: dict[str, Any],
    inner_session_id: str,
    parent_tool_use_id: str | None = None,
) -> dict[str, Any]:
    inner: dict[str, Any] = {
        "type": "stream_event",
        "event": raw_event,
        "session_id": inner_session_id,
        "parent_tool_use_id": parent_tool_use_id,
        "uuid": str(uuid.uuid4()),
    }
    return _koraku_envelope_event(inner)


def _wrap_user_event(
    message: dict[str, Any],
    inner_session_id: str,
) -> dict[str, Any]:
    parent: str | None = None
    for block in message.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            parent = block.get("tool_use_id")
            break
    inner: dict[str, Any] = {
        "type": "user",
        "message": message,
        "session_id": inner_session_id,
        "parent_tool_use_id": parent,
        "uuid": str(uuid.uuid4()),
    }
    return _koraku_envelope_event(inner)


def _result_inner(
    *,
    inner_session_id: str,
    model: str,
    failed: bool,
    stop_reason: str,
    duration_ms: int,
    duration_api_ms: int,
) -> dict[str, Any]:
    return {
        "type": "result",
        "subtype": "error" if failed else "success",
        "duration_ms": duration_ms,
        "duration_api_ms": duration_api_ms,
        "is_error": failed,
        "result": "",
        "session_id": inner_session_id,
        "uuid": str(uuid.uuid4()),
        "total_cost_usd": 0.0,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
        "stop_reason": stop_reason,
        "modelUsage": {
            model: {
                "inputTokens": 0,
                "outputTokens": 0,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
                "webSearchRequests": 0,
                "costUSD": 0.0,
                "contextWindow": 200000,
            }
        },
    }


def _koraku_completed(
    *,
    pty_session_id: str,
    sandbox_id: str,
    exit_code: int,
    failed: bool,
    error: str | None,
) -> dict[str, Any]:
    return {
        "type": "koraku.completed",
        "data": {
            "ptySessionId": pty_session_id,
            "sandboxId": sandbox_id,
            "exitCode": exit_code,
            "failed": failed,
            "error": error,
            "postflightBackgrounded": False,
        },
    }


def _koraku_output_marker() -> dict[str, Any]:
    return {"type": "koraku.output", "data": {"marker": "__KORAKU_DONE__:0"}}


def _koraku_trace(trace: str, data: dict[str, Any], inner_session_id: str) -> dict[str, Any]:
    inner = {"type": "koraku.trace", "trace": trace, "data": data, "session_id": inner_session_id, "uuid": str(uuid.uuid4())}
    return _koraku_envelope_event(inner)


@dataclass
class KorakuStreamState:
    """Per-request stream envelope ids and timing."""

    pty_session_id: str = field(default_factory=new_pty_session_id)
    sandbox_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    inner_session_id: str = field(default_factory=new_inner_session_id)
    started_ms: int = field(default_factory=_now_ms)
    resolved_model: str = ""
    eff_provider: str = ""

    def started_payload(self, model: str, *, chat_session_id: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "ptySessionId": self.pty_session_id,
            "sandboxId": self.sandbox_id,
            "model": model,
            "startedAt": self.started_ms,
        }
        if chat_session_id:
            data["chatSessionId"] = chat_session_id
        return {"type": "koraku.started", "data": data}

    def s2_stream_payload(self) -> dict[str, Any]:
        uri = f"s2://koraku/{self.pty_session_id}"
        return {"type": "koraku.s2-stream", "data": {"uri": uri}}

    def route_decision_payload(self) -> dict[str, Any]:
        return {
            "type": "koraku.route_decision",
            "data": route_decision_data(self.eff_provider, self.resolved_model),
        }

    def system_init_payload(self, cwd: str, koraku: dict[str, Any]) -> dict[str, Any]:
        inner = build_system_init_inner(
            cwd=cwd,
            inner_session_id=self.inner_session_id,
            model=self.resolved_model,
            koraku=koraku,
        )
        return _koraku_envelope_event(inner)

    def completion_sequence(self, data: dict[str, Any] | None, *, failed: bool, error: str | None) -> list[dict[str, Any]]:
        model = (data or {}).get("model") or self.resolved_model or "auto"
        reason = (data or {}).get("reason") or ("error" if failed else "end_turn")
        elapsed = max(0, _now_ms() - self.started_ms)
        out: list[dict[str, Any]] = []
        out.append(_koraku_envelope_event(_result_inner(
            inner_session_id=self.inner_session_id,
            model=model,
            failed=failed,
            stop_reason="error" if failed else str(reason),
            duration_ms=elapsed,
            duration_api_ms=elapsed,
        )))
        out.append(_koraku_completed(
            pty_session_id=self.pty_session_id,
            sandbox_id=self.sandbox_id,
            exit_code=1 if failed else 0,
            failed=failed,
            error=error,
        ))
        out.append(_koraku_output_marker())
        return out


def map_koraku_stream_events(event: dict[str, Any], state: KorakuStreamState) -> list[dict[str, Any]]:
    """Translate one Koraku queue event into zero or more outer SSE JSON objects."""
    et = event.get("type")
    if et == "agent.mode":
        return [_koraku_trace("mode", event.get("data") or {}, state.inner_session_id)]
    if et == "agent.studio":
        return [_koraku_trace("studio", event.get("data") or {}, state.inner_session_id)]
    if et == "agent.tools":
        return [_koraku_trace("tools", event.get("data") or {}, state.inner_session_id)]
    if et == "agent.context":
        return [_koraku_trace("context", event.get("data") or {}, state.inner_session_id)]
    if et == "tool_execution":
        return [_koraku_trace("tool_execution", event.get("data") or {}, state.inner_session_id)]
    if et == "agent.memory":
        return [_koraku_trace("memory", event.get("data") or {}, state.inner_session_id)]
    if et == "stream_event":
        raw = event.get("event")
        if not isinstance(raw, dict):
            return []
        return [_wrap_stream_event(raw, state.inner_session_id, None)]
    if et == "user":
        msg = event.get("message")
        if not isinstance(msg, dict):
            return []
        return [_wrap_user_event(msg, state.inner_session_id)]
    if et == "agent.completed":
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        return state.completion_sequence(data, failed=False, error=None)
    if et == "agent.error":
        err = str((event.get("data") or {}).get("error", "unknown error"))
        return state.completion_sequence(None, failed=True, error=err)
    return []
