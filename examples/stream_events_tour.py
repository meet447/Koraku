#!/usr/bin/env python3
"""Tour of KorakuEvent types during a short agent run."""
from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import require_llm_config

from koraku import EventType, Koraku


def _describe(event) -> str:
    if event.type == EventType.stream_event:
        inner = event.llm.type if event.llm else "?"
        if event.stream_chunk:
            return f"stream:{inner} chunk={event.stream_chunk!r}"
        if event.text:
            return f"stream:{inner} text={event.text[:60]!r}"
        return f"stream:{inner}"
    if event.completed is not None:
        return f"completed reason={event.completed.reason} steps={event.completed.steps}"
    if event.error is not None:
        return f"error={event.error.error!r}"
    if event.question is not None:
        return f"question id={event.question.interaction_id}"
    if event.approval is not None:
        return f"approval tool={event.approval.tool}"
    if event.subagent is not None:
        return f"subagent phase={event.subagent.phase}"
    if event.action is not None:
        return f"action id={event.action.action_id}"
    if event.run_log_path:
        return f"run_log path={event.run_log_path}"
    return event.type


async def main() -> None:
    agent = Koraku(require_llm_config())
    counts: Counter[str] = Counter()

    async for event in agent.stream_events("Reply with exactly: tour-ok"):
        counts[event.type] += 1
        print(_describe(event))

    print("\n--- summary ---")
    for etype, n in sorted(counts.items()):
        print(f"  {etype}: {n}")


if __name__ == "__main__":
    asyncio.run(main())
