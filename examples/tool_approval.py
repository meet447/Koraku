#!/usr/bin/env python3
"""confirm_sensitive mode: approve or deny Write tool calls."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import print_stream_chunk, require_llm_config

from koraku import EventType, Koraku, PermissionModes


async def main() -> None:
    agent = Koraku(require_llm_config(permission_mode=PermissionModes.confirm_sensitive))
    rel_path = "notes/approval-demo.txt"
    prompt = (
        f"Create a short one-line note in `{rel_path}` using the Write tool, "
        "then confirm the file path in your reply."
    )

    async for event in agent.stream_events(prompt):
        if event.type == EventType.agent.approval and event.approval is not None:
            approval = event.approval
            print("\n--- approval required ---")
            print("tool:", approval.tool)
            print("input:", approval.tool_input)
            Koraku.approve_tool(approval.interaction_id, approved=True)
        else:
            print_stream_chunk(event)
            if event.completed is not None:
                print(f"\n--- done ({event.completed.reason}) ---")
            elif event.error is not None:
                print("\nERROR:", event.error.error, file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
