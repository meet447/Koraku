"""MCP workspace config."""
from __future__ import annotations

import json
from pathlib import Path

from koraku.mcp.config import load_mcp_config, mcp_servers_for_ui


def test_load_mcp_config(tmp_path: Path) -> None:
    cfg_path = tmp_path / ".koraku" / "mcp.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(
        json.dumps(
            {
                "servers": [
                    {"name": "demo", "command": "echo", "args": ["mcp"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    servers = load_mcp_config(str(tmp_path))
    assert len(servers) == 1
    assert servers[0].name == "demo"
    ui = mcp_servers_for_ui(str(tmp_path))
    assert ui[0]["name"] == "demo"
