"""Host file tools stay inside the server workspace."""

from __future__ import annotations

import pytest

from src.tools.registry import _read, _write


@pytest.mark.asyncio
async def test_read_rejects_path_outside_workspace(tmp_path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("secret-ish", encoding="utf-8")

    result = await _read(str(outside))

    assert result.startswith("Error: Path must stay under workspace:")


@pytest.mark.asyncio
async def test_write_rejects_path_outside_workspace(tmp_path) -> None:
    result = await _write(str(tmp_path / "new.txt"), "nope")

    assert result.startswith("Error: Path must stay under workspace:")
