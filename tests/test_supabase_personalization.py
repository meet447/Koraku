"""Personalization from Supabase is reflected in the system prompt."""
from __future__ import annotations

from src.agent.run import build_system_prompt


def test_build_system_prompt_account_profile_branch() -> None:
    s = build_system_prompt(
        "/tmp/ws",
        account_personalization={
            "agent_name": "HelperX",
            "memory": "User prefers concise answers.",
            "soul": "Warm and direct.",
        },
    )
    assert "HelperX" in s
    assert "User prefers concise answers." in s
    assert "Warm and direct." in s
    assert "Koraku account profile" in s
