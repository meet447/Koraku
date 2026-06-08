"""Example: general-purpose subagents via the Task tool."""
from __future__ import annotations

import asyncio

from koraku import AgentDefinition, Koraku, KorakuConfig


async def main() -> None:
    agent = Koraku(
        KorakuConfig(
            fireworks_api_key="YOUR_KEY",
            llm_provider="fireworks",
            agents={
                "researcher": AgentDefinition(
                    description="Gathers facts from the web and workspace files.",
                    prompt="You are a focused researcher. Search and read; summarize findings.",
                    tools=("WebSearch", "WebFetch", "Read", "Glob", "Grep", "Write"),
                    max_steps=12,
                ),
                "writer": AgentDefinition(
                    description="Turns research notes into a polished summary.",
                    prompt="You are a concise writer. Use prior research; produce clear prose.",
                    tools=("Read", "Write", "Glob"),
                    max_steps=8,
                ),
            },
        )
    )

    prompt = (
        "Research current trends in local-first AI assistants, save notes under "
        "`notes/research.md`, then delegate to the writer for a one-paragraph summary."
    )

    async for event in agent.stream(prompt):
        et = event.get("type")
        if et == "agent.subagent":
            print("subagent:", event.get("data"))
        elif et == "agent.completed":
            print("done:", event.get("data"))


if __name__ == "__main__":
    asyncio.run(main())
