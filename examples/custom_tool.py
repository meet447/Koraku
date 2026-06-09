#!/usr/bin/env python3
"""Register a custom Tool and let the agent call it."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import print_stream_chunk, require_llm_config

from koraku import Koraku, Tool


async def _echo_handler(query: str) -> str:
    return f"Echo says: {query}"


async def main() -> None:
    echo = Tool(
        name="Echo",
        description="Repeat the query string back with a prefix.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Text to echo"}},
            "required": ["query"],
        },
        handler=_echo_handler,
    )
    agent = Koraku(require_llm_config(), tools=[echo])
    prompt = 'Call the Echo tool once with query "koraku-sdk" and report the result in one sentence.'

    async for event in agent.stream_events(prompt):
        print_stream_chunk(event)
        if event.completed is not None:
            print(f"\n--- done ({event.completed.steps} steps) ---")


if __name__ == "__main__":
    asyncio.run(main())
