#!/usr/bin/env python3
"""AgentHooks: observe and gate tool calls in embedder apps."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import print_stream_chunk, require_llm_config

from koraku import Koraku
from koraku.agent.hooks import AgentHooks, HookResult, ToolCallContext


async def main() -> None:
    seen: list[str] = []

    async def pre_tool_use(ctx: ToolCallContext) -> HookResult | None:
        seen.append(ctx.tool_name)
        print(f"\n[hook] before {ctx.tool_name}({list(ctx.tool_input.keys())})")
        if ctx.tool_name == "Bash":
            return HookResult(allow=False, message="Bash disabled in this demo")
        return None

    async def post_tool_use(ctx: ToolCallContext, result: str, ok: bool) -> None:
        preview = result[:80].replace("\n", " ")
        print(f"[hook] after {ctx.tool_name} ok={ok}: {preview}")

    hooks = AgentHooks(pre_tool_use=pre_tool_use, post_tool_use=post_tool_use)
    chat = Koraku(require_llm_config()).session(hooks=hooks)

    prompt = (
        "Use Glob to list files matching '*.md' in the workspace root (one level). "
        "Reply with how many matches you found."
    )

    async for event in chat.send_and_stream_events(prompt):
        print_stream_chunk(event)
        if event.completed is not None:
            print(f"\n--- done; tools observed: {seen} ---")


if __name__ == "__main__":
    asyncio.run(main())
