"""Tests for workspace skill slash commands."""
from __future__ import annotations

from pathlib import Path

import pytest

from koraku.tools.skills import (
    list_skills,
    parse_slash_command,
    resolve_slash_invocation,
    slash_commands_for_ui,
)


def test_parse_slash_command() -> None:
    assert parse_slash_command("/weekly-review check inbox") == ("weekly-review", "check inbox")
    assert parse_slash_command("/solo") == ("solo", "")
    assert parse_slash_command("hello") is None


def test_resolve_slash_invocation(tmp_path: Path) -> None:
    skill_dir = tmp_path / ".koraku" / "skills" / "weekly-review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Weekly review\n\nSummarize todos and calendar.\n",
        encoding="utf-8",
    )
    inv = resolve_slash_invocation("/weekly-review focus on email", str(tmp_path))
    assert inv is not None
    assert inv.slug == "weekly-review"
    assert inv.user_message == "focus on email"
    assert "Weekly review" in inv.prompt_appendix


def test_unknown_skill_returns_none(tmp_path: Path) -> None:
    assert resolve_slash_invocation("/missing", str(tmp_path)) is None


def test_slash_commands_for_ui(tmp_path: Path) -> None:
    skill_dir = tmp_path / ".koraku" / "skills" / "solo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("Quick solo task flow.\n", encoding="utf-8")
    cmds = slash_commands_for_ui(str(tmp_path))
    assert cmds == [{"name": "solo", "description": "Quick solo task flow."}]
    assert list_skills(str(tmp_path))[0].slug == "solo"
