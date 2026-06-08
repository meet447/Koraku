#!/usr/bin/env python3
"""Minimal embed example — in-process Koraku agent (no HTTP server)."""
from __future__ import annotations

import asyncio
import os

from koraku import Koraku, KorakuConfig


async def main() -> None:
    provider = os.environ.get("LLM_PROVIDER", "fireworks").strip().lower()
    if provider == "anthropic":
        config = KorakuConfig.anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        )
    elif provider == "fireworks":
        config = KorakuConfig.fireworks(
            api_key=os.environ.get("FIREWORKS_API_KEY", ""),
            model=os.environ.get(
                "FIREWORKS_MODEL",
                "accounts/fireworks/models/kimi-k2p6",
            ),
        )
    else:
        config = KorakuConfig(
            llm_provider=provider,
            fireworks_api_key=os.environ.get("FIREWORKS_API_KEY", ""),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            llm_openai_compat_ids=os.environ.get("LLM_OPENAI_COMPAT_IDS", ""),
        )

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
