#!/usr/bin/env python3
"""LLM provider configuration patterns for SDK embedders."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from koraku import Koraku, KorakuConfig, ProviderInfo


def build_agent() -> Koraku:
    """Pick a configuration strategy (uncomment one block)."""

    if os.environ.get("FIREWORKS_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
        return Koraku(KorakuConfig.from_env())

    return Koraku(
        KorakuConfig.openai_compat(
            "ollama",
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
            model=os.environ.get("OLLAMA_MODEL", "llama3.2"),
        )
    )


async def main() -> None:
    agent = build_agent()
    providers: list[ProviderInfo] = agent.list_providers(detailed=True)
    for p in providers:
        status = "ok" if p.configured else "not configured"
        print(f"- {p.id} ({p.label}): {status}, default={p.default_model}")

    async for event in agent.stream_events("Reply with one word: ready"):
        if event.text:
            print(event.text, end="", flush=True)
        elif event.completed is not None:
            print("\nturn finished")
        elif event.error is not None:
            print("\nERROR:", event.error.error, file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
