#!/usr/bin/env python3
"""General-purpose subagents via the Task tool (researcher + writer)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import require_llm_config

from koraku import AgentDefinition, Koraku, KorakuConfig


async def main() -> None:
    base = require_llm_config()
    agent = Koraku(
        KorakuConfig(
            llm_provider=base.llm_provider,
            fireworks_api_key=base.fireworks_api_key,
            fireworks_model=base.fireworks_model,
            anthropic_api_key=base.anthropic_api_key,
            anthropic_model=base.anthropic_model,
            llm_openai_compat_ids=base.llm_openai_compat_ids,
            llm_openai_compat_json=base.llm_openai_compat_json,
            openai_compat_providers=base.openai_compat_providers,
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

    async for event in agent.stream_events(prompt):
        if event.subagent is not None:
            print("subagent:", event.subagent.phase, event.subagent.agent or event.subagent.toolkits)
        elif event.completed is not None:
            print("done:", event.completed.reason, event.completed.steps)
        elif event.error is not None:
            print("error:", event.error.error, file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
