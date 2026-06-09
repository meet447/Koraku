#!/usr/bin/env python3
"""Load SDK config from .env — one-shot text reply via stream_text()."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `python examples/from_env.py` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import require_llm_config

from koraku import Koraku


async def main() -> None:
    agent = Koraku(require_llm_config())
    text = await agent.stream_text("Say hello in five words or fewer.")
    print("assistant:", text)


if __name__ == "__main__":
    asyncio.run(main())
