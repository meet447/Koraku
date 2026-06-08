#!/usr/bin/env python3
"""Minimal embed example — in-process Koraku agent (no HTTP server)."""
from __future__ import annotations

import asyncio

from koraku import Koraku, KorakuConfig


async def main() -> None:
    config = KorakuConfig.from_env(execution_target="local")
    agent = Koraku(config)
    print("providers:", agent.list_providers())

    async for event in agent.stream("Say hello in one short sentence."):
        typ = event.get("type")
        if typ == "agent.completed":
            print("DONE:", event.get("data"))
        elif typ in ("agent.error", "agent.warning"):
            print(typ.upper(), event.get("data"))


if __name__ == "__main__":
    asyncio.run(main())
