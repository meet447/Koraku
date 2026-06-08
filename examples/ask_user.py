"""Example: AskUser + permission modes with the in-process SDK."""
from __future__ import annotations

import asyncio

from koraku import Koraku, KorakuConfig


async def main() -> None:
    agent = Koraku(
        KorakuConfig(
            fireworks_api_key="YOUR_KEY",
            llm_provider="fireworks",
            permission_mode="plan",
        )
    )

    async def handle_turn(prompt: str) -> None:
        async for event in agent.stream(prompt):
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
                # Demo: pick the first option for each question.
                answers = {}
                for q in questions:
                    header = str(q.get("header") or "Answer")
                    opts = q.get("options") or []
                    answers[header] = str((opts[0] or {}).get("label") or "Yes")
                Koraku.respond_to_interaction(iid, {"answers": answers})
            elif et == "agent.completed":
                print("\n--- done ---", event.get("data"))

    await handle_turn("Help me plan a weekly review routine. Ask me 2 clarifying questions first.")


if __name__ == "__main__":
    asyncio.run(main())
