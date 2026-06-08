#!/usr/bin/env python3
"""Example: load SDK config from .env and use stream_text()."""
from __future__ import annotations

import asyncio

from koraku import Koraku, KorakuConfig


async def main() -> None:
    # Reads LLM_PROVIDER, FIREWORKS_API_KEY, etc. from the environment / .env
    agent = Koraku(KorakuConfig.from_env())

    text = await agent.stream_text("Say hello in five words or fewer.")
    print("assistant:", text)


if __name__ == "__main__":
    asyncio.run(main())
