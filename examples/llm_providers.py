"""Example: LLM provider configuration patterns for SDK embedders."""
from __future__ import annotations

import asyncio
import os

from koraku import Koraku, KorakuConfig, OpenAICompatProvider
from koraku.llm import register_openai_compat_provider


async def main() -> None:
    # 1) Preset helpers
    # agent = Koraku(KorakuConfig.fireworks(api_key="...", model="accounts/fireworks/models/kimi-k2p6"))
    # agent = Koraku(KorakuConfig.anthropic(api_key="...", model="claude-3-5-sonnet-20241022"))

    # 2) OpenAI-compatible endpoint (Ollama, vLLM, OpenAI, Groq, …)
    agent = Koraku(
        KorakuConfig.openai_compat(
            "ollama",
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
            model=os.environ.get("OLLAMA_MODEL", "llama3.2"),
        )
    )

    # 3) Process-wide registration (optional; useful before multiple Koraku instances)
    # register_openai_compat_provider(OpenAICompatProvider(
    #     id="groq",
    #     label="Groq",
    #     base_url="https://api.groq.com/openai/v1",
    #     api_key=os.environ["GROQ_API_KEY"],
    #     default_model="llama-3.3-70b-versatile",
    #     models=("llama-3.3-70b-versatile",),
    # ))
    # agent = Koraku(KorakuConfig(llm_provider="groq"))

    print("configured providers:", agent.list_providers(detailed=True))

    async for event in agent.stream("Reply with one word: ready"):
        if event.get("type") == "agent.completed":
            print("turn finished")


if __name__ == "__main__":
    asyncio.run(main())
