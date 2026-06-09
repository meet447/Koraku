#!/usr/bin/env python3
"""Multi-turn chat with KorakuSession and session text helpers."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import require_llm_config

from koraku import Koraku


async def main() -> None:
    koraku = Koraku(require_llm_config())

    async with koraku.session() as chat:
        print("session:", chat.session_id)

        for user_msg in ("My name is Alex.", "What's my name?"):
            print("\nuser:", user_msg)
            async for event in chat.send_and_stream_events(user_msg):
                if event.text:
                    print(event.text, end="", flush=True)
                elif event.completed is not None:
                    print("\nturn done")
            print("last assistant:", chat.state.last_assistant_text()[:200])


if __name__ == "__main__":
    asyncio.run(main())
