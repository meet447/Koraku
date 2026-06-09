#!/usr/bin/env python3
"""AskUser + plan permission mode with typed stream events."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import print_stream_chunk, require_llm_config

from koraku import EventType, Koraku, KorakuEvent


async def main() -> None:
    agent = Koraku(require_llm_config(permission_mode="plan"))
    prompt = (
        "Before suggesting anything, you MUST call the AskUser tool with exactly 2 questions "
        "(each with 2–3 short options). Do not answer in plain text until after AskUser returns."
    )

    events: list[KorakuEvent] = []
    async for event in agent.stream_events(prompt):
        events.append(event)
        if event.type == EventType.agent.question and event.question is not None:
            qdata = event.question
            print("\n--- AskUser ---")
            for q in qdata.questions:
                print(q.header, ":", q.text)
                for opt in q.options:
                    print(" ", "-", opt.label)
            answers = {q.header: (q.options[0].label if q.options else "Yes") for q in qdata.questions}
            Koraku.answer_question(qdata.interaction_id, answers)
        elif event.is_stream_event:
            print_stream_chunk(event)
        elif event.completed is not None:
            print("\n\n--- done ---", event.completed.reason, f"({event.completed.steps} steps)")

    if events and not any(e.is_question for e in events):
        print(
            "\n(note: the model replied without calling AskUser; try a stricter prompt or re-run)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    asyncio.run(main())
