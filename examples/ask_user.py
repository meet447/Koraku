"""Example: AskUser + permission modes with the in-process SDK."""
from __future__ import annotations

import asyncio
import sys

from koraku import Koraku, KorakuConfig
from koraku.sdk_events import assistant_text_blocks, collect_assistant_text


async def main() -> None:
    cfg = KorakuConfig.from_env(permission_mode="plan")
    if not (cfg.fireworks_api_key or cfg.anthropic_api_key):
        print(
            "Set FIREWORKS_API_KEY or ANTHROPIC_API_KEY in .env (or pass a key in KorakuConfig).",
            file=sys.stderr,
        )
        sys.exit(1)

    agent = Koraku(cfg)
    prompt = (
        "Before suggesting anything, you MUST call the AskUser tool with exactly 2 questions "
        "(each with 2–3 short options). Do not answer in plain text until after AskUser returns."
    )

    events: list[dict] = []
    async for event in agent.stream(prompt):
        events.append(event)
        et = event.get("type")
        if et == "agent.question":
            data = event.get("data") or {}
            iid = str(data.get("interaction_id") or "")
            questions = data.get("questions") or []
            print("\n--- AskUser ---")
            for q in questions:
                print(q.get("header"), ":", q.get("question"))
                for opt in q.get("options") or []:
                    print(" ", "-", opt.get("label"))
            answers = {}
            for q in questions:
                header = str(q.get("header") or "Answer")
                opts = q.get("options") or []
                answers[header] = str((opts[0] or {}).get("label") or "Yes")
            Koraku.respond_to_interaction(iid, {"answers": answers})
        elif et == "stream_event":
            for chunk in assistant_text_blocks(event):
                if chunk:
                    print(chunk, end="", flush=True)
        elif et == "agent.completed":
            print("\n\n--- done ---", event.get("data"))

    text = collect_assistant_text(events)
    if text and "AskUser" not in text:
        print(
            "\n(note: the model replied without calling AskUser; try a stricter prompt or re-run)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    asyncio.run(main())
