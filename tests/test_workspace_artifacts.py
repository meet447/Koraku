"""Koraku task-room artifact helpers and tools."""

from __future__ import annotations

import json

import pytest

from src.tools.registry import _artifact_list, _artifact_read, _artifact_write
from src.workspace.artifacts import (
    host_artifact_abs_path,
    normalize_run_slug,
    safe_artifact_relpath,
)


def test_normalize_run_slug() -> None:
    assert normalize_run_slug(" Vendor Research: April 2026! ") == "vendor-research-april-2026"
    assert normalize_run_slug("   ") == "koraku-task"


def test_safe_artifact_relpath_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        safe_artifact_relpath("x", "../secret.txt")


@pytest.mark.asyncio
async def test_artifact_write_read_and_list(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    out = await _artifact_write(
        "Daily Driver Test",
        "plan.md",
        "# Plan\n\n- Scout\n- Analyst\n",
        artifact_type="plan",
    )
    data = json.loads(out)

    assert data["ok"] is True
    assert data["artifact"]["path"] == ".koraku/runs/daily-driver-test/plan.md"
    assert host_artifact_abs_path(tmp_path, "Daily Driver Test", "plan.md").endswith(
        ".koraku/runs/daily-driver-test/plan.md"
    )

    read = await _artifact_read("Daily Driver Test", "plan.md")
    assert "# Plan" in read

    listed = await _artifact_list("Daily Driver Test", "*.md")
    assert "plan.md" in listed
