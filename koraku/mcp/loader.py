"""Connect to stdio MCP servers and expose their tools for one agent run."""
from __future__ import annotations

import logging
import re
from contextlib import AsyncExitStack
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any

from koraku.mcp.config import McpServerConfig, load_mcp_config
from koraku.tools.tool_def import Tool

log = logging.getLogger(__name__)

_SAFE = re.compile(r"[^a-zA-Z0-9_]+")

_mcp_runtime: ContextVar[McpRunRuntime | None] = ContextVar("koraku_mcp_runtime", default=None)


@dataclass
class McpServerRuntime:
    name: str
    stack: AsyncExitStack = field(default_factory=AsyncExitStack)


@dataclass
class McpRunRuntime:
    servers: list[McpServerRuntime] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    async def close(self) -> None:
        for srv in reversed(self.servers):
            try:
                await srv.stack.aclose()
            except Exception as e:
                log.debug("mcp server %s close: %s", srv.name, e)
        self.servers.clear()


def bind_mcp_runtime(runtime: McpRunRuntime | None) -> Token[McpRunRuntime | None]:
    return _mcp_runtime.set(runtime)


def reset_mcp_runtime(token: Token[McpRunRuntime | None]) -> None:
    _mcp_runtime.reset(token)


def _tool_name(server: str, raw_name: str) -> str:
    base = f"mcp_{server}_{raw_name}"
    return _SAFE.sub("_", base)[:120]


async def start_mcp_runtime(workspace: str | None = None) -> tuple[McpRunRuntime, list[Tool]]:
    runtime = McpRunRuntime()
    configs = load_mcp_config(workspace)
    if not configs:
        return runtime, []
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        runtime.warnings.append(
            "MCP servers are configured in .koraku/mcp.json but the `mcp` package is not installed. "
            "Install with: pip install 'koraku[mcp]'"
        )
        return runtime, []

    tools: list[Tool] = []
    for cfg in configs:
        try:
            server_tools, server_runtime = await _connect_server(
                cfg, ClientSession, StdioServerParameters, stdio_client
            )
            runtime.servers.append(server_runtime)
            tools.extend(server_tools)
        except Exception as e:
            msg = f"MCP server `{cfg.name}` failed: {e}"
            log.warning(msg)
            runtime.warnings.append(msg)
    return runtime, tools


async def _connect_server(
    cfg: McpServerConfig,
    ClientSession: Any,
    StdioServerParameters: Any,
    stdio_client: Any,
) -> tuple[list[Tool], McpServerRuntime]:
    server_runtime = McpServerRuntime(name=cfg.name)
    stack = server_runtime.stack
    params = StdioServerParameters(command=cfg.command, args=list(cfg.args), env=cfg.env or None)
    read, write = await stack.enter_async_context(stdio_client(params))
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    listed = await session.list_tools()
    mcp_tools = listed.tools if hasattr(listed, "tools") else []
    out: list[Tool] = []
    for raw in mcp_tools or []:
        raw_name = getattr(raw, "name", None) or ""
        if not raw_name:
            continue
        description = getattr(raw, "description", None) or raw_name
        schema = getattr(raw, "inputSchema", None)
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        koraku_name = _tool_name(cfg.name, str(raw_name))

        def _make_handler(sess: Any, raw: str):
            async def _handler(**kwargs: Any) -> str:
                result = await sess.call_tool(raw, arguments=kwargs or {})
                content = getattr(result, "content", None) or []
                parts: list[str] = []
                for block in content:
                    text = getattr(block, "text", None)
                    if text:
                        parts.append(str(text))
                return "\n".join(parts) if parts else str(result)

            return _handler

        out.append(
            Tool(
                name=koraku_name,
                description=f"[MCP:{cfg.name}] {description}",
                input_schema=schema,
                handler=_make_handler(session, str(raw_name)),
                categories=["mcp", cfg.name],
            )
        )
    return out, server_runtime
