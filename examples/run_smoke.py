#!/usr/bin/env python3
"""Run all example scripts that need an LLM (requires .env)."""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

EXAMPLES = [
    "from_env.py",
    "embed_python.py",
    "multi_turn_session.py",
    "llm_providers.py",
    "stream_events_tour.py",
    "custom_tool.py",
    "agent_hooks.py",
    "tool_approval.py",
    "ask_user.py",
    "research_subagents.py",
]


def main() -> int:
    root = Path(__file__).resolve().parent
    repo = root.parent
    python = sys.executable
    failed: list[str] = []

    for name in EXAMPLES:
        path = root / name
        print(f"\n{'=' * 60}\n>>> {name}\n{'=' * 60}")
        result = subprocess.run(
            [python, str(path)],
            cwd=repo,
            check=False,
        )
        if result.returncode != 0:
            failed.append(name)

    print(f"\n{'=' * 60}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print(f"All {len(EXAMPLES)} examples passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
