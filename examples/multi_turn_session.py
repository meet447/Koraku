"""Example: multi-turn chat with KorakuSession (send / stream)."""
from __future__ import annotations

import asyncio

from koraku import Koraku, KorakuConfig


async def main() -> None:
    koraku = Koraku(KorakuConfig(fireworks_api_key="YOUR_KEY", llm_provider="fireworks"))

    async with koraku.session() as chat:
        print("session:", chat.session_id)

        for user_msg in ("My name is Alex.", "What's my name?"):
            print("\nuser:", user_msg)
            await chat.send(user_msg)
            async for event in chat.stream():
                if event.get("type") == "agent.completed":
                    print("turn done:", event.get("data"))
                if event.get("type") == "stream_event":
                    inner = (event.get("event") or {})
                    if inner.get("type") == "assistant_message":
                        for block in inner.get("message", {}).get("content", []):
                            if block.get("type") == "text":
                                print("assistant:", block.get("text", "")[:200])


if __name__ == "__main__":
    asyncio.run(main())
