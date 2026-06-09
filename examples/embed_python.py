#!/usr/bin/env python3
"""Minimal in-process embed — stream events with typed KorakuEvent API."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import require_llm_config

from koraku import ExecutionTargets, Koraku, PermissionModes


async def main() -> None:
    agent = Koraku(
        require_llm_config(
            execution_target=ExecutionTargets.local,
            permission_mode=PermissionModes.default,
        )
    )
    providers = agent.list_providers(detailed=True)
    print("providers:", [p.id for p in providers])

    async for event in agent.stream_events("Say hello in one short sentence."):
        if event.text:
            print(event.text, end="", flush=True)
        elif event.completed is not None:
            print(f"\nDONE: {event.completed.reason} ({event.completed.steps} steps)")
        elif event.error is not None:
            print(f"\nERROR: {event.error.error}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
