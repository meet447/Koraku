"""Composio: OAuth connections + dynamic tools for connected integrations (Gmail, Drive, …)."""
from __future__ import annotations

import copy
import json
import os
import re
import time
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Callable, Coroutine

from src.core.config import settings
from src.tools.tool_def import Tool

_TOOLKIT_SLUG_SAFE = re.compile(r"^[A-Z0-9][A-Z0-9_]{1,63}$")

_composio_client: Any = None
_workspace_for_client: str = ""
_composio_tool_map: ContextVar[dict[str, Tool] | None] = ContextVar("koraku_composio_tools", default=None)
_connections_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_TTL = 15.0


def effective_api_key() -> str:
    """Key from pydantic settings (repo ``.env``) or process environment (IDE / shell)."""
    return (settings.composio_api_key or os.environ.get("COMPOSIO_API_KEY", "") or "").strip()


def is_configured() -> bool:
    return bool(effective_api_key())


def configure_workspace_cache(workspace: str) -> None:
    """Composio SDK requires a writable ``COMPOSIO_CACHE_DIR`` before first import."""
    global _composio_client, _workspace_for_client
    root = Path(workspace).resolve()
    cache = root / ".koraku" / "composio-cache"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["COMPOSIO_CACHE_DIR"] = str(cache)
    ws = str(root)
    if ws != _workspace_for_client:
        _composio_client = None
        _workspace_for_client = ws


def _client() -> Any:
    global _composio_client
    if not is_configured():
        raise RuntimeError("COMPOSIO_API_KEY is not set")
    if _composio_client is None:
        from composio import Composio  # lazy: needs COMPOSIO_CACHE_DIR

        _composio_client = Composio(api_key=effective_api_key())
    return _composio_client


def user_id() -> str:
    return (
        (settings.composio_user_id or os.environ.get("COMPOSIO_USER_ID") or "koraku-local").strip()
        or "koraku-local"
    )


def list_connections_summary() -> list[dict[str, Any]]:
    """All connections for the configured Koraku user (any status)."""
    if not is_configured():
        return []

    uid = user_id()
    now = time.monotonic()

    if uid in _connections_cache:
        cache_time, cached_data = _connections_cache[uid]
        if (now - cache_time) < _CACHE_TTL:
            # Return a copy to prevent mutation of the cached data
            return copy.deepcopy(cached_data)

    c = _client()
    resp = c.connected_accounts.list(user_ids=[uid], limit=80.0)
    out: list[dict[str, Any]] = []
    for item in resp.items:
        slug = getattr(item.toolkit, "slug", "") or ""
        name = getattr(item.toolkit, "name", "") or slug
        out.append({
            "id": item.id,
            "status": item.status,
            "toolkit_slug": slug,
            "toolkit_name": name,
            "is_disabled": item.is_disabled,
        })

    _connections_cache[uid] = (time.monotonic(), out)
    return out


def active_toolkit_slugs() -> list[str]:
    """Toolkits with at least one ACTIVE, non-disabled connection."""
    slugs: list[str] = []
    for row in list_connections_summary():
        if row.get("status") == "ACTIVE" and not row.get("is_disabled"):
            s = (row.get("toolkit_slug") or "").strip().upper()
            if s and s not in slugs:
                slugs.append(s)
    return slugs


def start_toolkit_auth(toolkit: str, *, callback_url: str | None = None) -> dict[str, Any]:
    """Begin OAuth / Composio Link for a toolkit; returns redirect URL when applicable."""
    # callback_url: reserved for future explicit OAuth return URLs; managed auth uses Composio-hosted flow.
    _ = callback_url
    if not is_configured():
        raise RuntimeError("Composio is not configured")
    slug = toolkit.strip().upper()
    if not _TOOLKIT_SLUG_SAFE.match(slug):
        raise ValueError("Invalid toolkit slug")
    c = _client()
    req = c.toolkits.authorize(user_id=user_id(), toolkit=slug)
    return {
        "connection_request_id": req.id,
        "status": req.status,
        "redirect_url": req.redirect_url,
    }


def search_toolkits(query: str | None, *, limit: int = 48) -> list[dict[str, str]]:
    if not is_configured():
        return []
    c = _client()
    q = (query or "").strip()
    params: dict[str, Any] = {"limit": float(min(max(limit, 1), 50))}
    if q:
        params["search"] = q
    items = c.toolkits.get(query=params)
    out: list[dict[str, str]] = []
    for it in items:
        meta = getattr(it, "meta", None)
        desc = ""
        if meta is not None:
            desc = str(getattr(meta, "description", "") or "")
        out.append({
            "slug": it.slug,
            "name": it.name,
            "description": desc[:240],
        })
    return out


def _normalize_input_schema(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {"type": "object", "properties": {}, "required": []}
    if raw.get("type") == "object":
        return raw
    if "properties" in raw:
        return {"type": "object", **{k: v for k, v in raw.items() if k in ("properties", "required", "additionalProperties", "description")}}
    return {"type": "object", "properties": dict(raw), "required": []}


def _execute_factory(slug: str) -> Callable[..., Coroutine[Any, Any, str]]:
    async def _run(**kwargs: Any) -> str:
        return await _execute_composio_tool(slug, kwargs)

    return _run


async def _execute_composio_tool(slug: str, arguments: dict[str, Any]) -> str:
    if not is_configured():
        return "Error: Composio is not configured (set COMPOSIO_API_KEY)."
    try:
        c = _client()
        # Composio SDK refuses ``version="latest"`` unless ``dangerously_skip_version_check`` is set.
        # Pin to the catalog version when available so the API gets a concrete toolkit version.
        version: str | None = None
        try:
            meta = c.tools.get_raw_composio_tool_by_slug(slug)
            v = getattr(meta, "version", None) if meta is not None else None
            if isinstance(v, str) and v.strip() and v.strip().lower() != "latest":
                version = v.strip()
        except Exception:
            pass
        res = c.tools.execute(
            slug=slug,
            arguments=dict(arguments or {}),
            user_id=user_id(),
            version=version,
            dangerously_skip_version_check=True,
        )
        if hasattr(res, "model_dump"):
            res = res.model_dump()
    except Exception as e:
        return f"Error: Composio execute failed: {e}"
    if not isinstance(res, dict):
        return f"Error: unexpected Composio response type: {type(res).__name__}"
    if res.get("successful"):
        try:
            return json.dumps(res.get("data"), indent=2, default=str)[:80_000]
        except (TypeError, ValueError):
            return str(res.get("data"))[:80_000]
    err = res.get("error") or "unknown_error"
    return f"Error: {err}"


def build_dynamic_composio_tools() -> list[Tool]:
    """Anthropic-shaped tools for active integrations only."""
    if not is_configured():
        return []
    tk_slugs = active_toolkit_slugs()
    if not tk_slugs:
        return []
    c = _client()
    limit = max(8, min(int(settings.composio_tools_limit), 120))
    raw = c.tools.get_raw_composio_tools(toolkits=tk_slugs, limit=limit)
    tools: list[Tool] = []
    for t in raw:
        if getattr(t, "is_deprecated", False):
            continue
        slug = t.slug
        desc = (t.human_description or t.description or "").strip() or f"Composio action `{slug}`"
        if len(desc) > 900:
            desc = desc[:897] + "…"
        schema = _normalize_input_schema(dict(t.input_parameters or {}))
        toolkit = getattr(t.toolkit, "slug", "") if t.toolkit else ""
        full_desc = f"[{toolkit}] {desc}" if toolkit else desc
        tools.append(
            Tool(
                name=slug,
                description=full_desc,
                input_schema=schema,
                handler=_execute_factory(slug),
                categories=["composio", toolkit.lower() if toolkit else "composio"],
            )
        )
    return tools


def push_composio_tool_registry(tools: list[Tool]) -> Token | None:
    if not tools:
        return None
    return _composio_tool_map.set({t.name: t for t in tools})


def reset_composio_tool_registry(token: Token | None) -> None:
    if token is not None:
        _composio_tool_map.reset(token)


def get_registered_composio_tool(name: str) -> Tool | None:
    m = _composio_tool_map.get()
    if not m:
        return None
    return m.get(name)


def composio_system_prompt_section() -> str:
    """Injected into the Koraku system prompt when Composio is available."""
    if not is_configured():
        return ""
    lines = [
        "## Connected integrations (Composio)",
        f"- Koraku user id for Composio: `{user_id()}`",
        "- When the user asks to use Gmail, Google Drive, Slack, etc., prefer the **Composio** tools "
        "(names like `GMAIL_*`, `GOOGLEDRIVE_*`) that appear in your tool list — they run with the "
        "accounts connected in the Koraku **Connections** page.",
        "- If a Composio tool returns an auth error, tell the user to open **Connections** and reconnect the service.",
    ]
    active = active_toolkit_slugs()
    if active:
        lines.append(f"- Currently **active** toolkits: {', '.join(active)}.")
    else:
        lines.append(
            "- No integrations are **ACTIVE** yet. Suggest opening **Connections** in the app to connect Gmail, "
            "Google Drive, or other services."
        )
    return "\n".join(lines) + "\n\n"
