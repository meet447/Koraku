"""Load MCP server definitions from the workspace."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from koraku.workspace.paths import workspace_dir


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    command: str
    args: tuple[str, ...]
    env: dict[str, str]


def mcp_config_path(workspace: str | None = None) -> Path:
    root = Path(workspace or workspace_dir()).resolve()
    return root / ".koraku" / "mcp.json"


def load_mcp_config(workspace: str | None = None) -> list[McpServerConfig]:
    path = mcp_config_path(workspace)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    servers = raw.get("servers") if isinstance(raw, dict) else raw
    if not isinstance(servers, list):
        return []
    out: list[McpServerConfig] = []
    for item in servers:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        command = str(item.get("command") or "").strip()
        if not name or not command:
            continue
        args_raw = item.get("args") or []
        args = tuple(str(x) for x in args_raw) if isinstance(args_raw, list) else ()
        env_raw = item.get("env") or {}
        env = {str(k): str(v) for k, v in env_raw.items()} if isinstance(env_raw, dict) else {}
        out.append(McpServerConfig(name=name, command=command, args=args, env=env))
    return out


def mcp_servers_for_ui(workspace: str | None = None) -> list[dict[str, Any]]:
    return [
        {"name": srv.name, "command": srv.command, "args": list(srv.args)}
        for srv in load_mcp_config(workspace)
    ]
