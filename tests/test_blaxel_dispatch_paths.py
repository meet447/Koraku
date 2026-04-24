"""Blaxel path mapping must not call ``PurePosixPath.resolve`` (not implemented)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def dispatch(monkeypatch: pytest.MonkeyPatch):
    import src.tools.blaxel_dispatch as bd

    monkeypatch.setattr(bd, "settings", SimpleNamespace(blaxel_sandbox_workdir="/tmp"))
    monkeypatch.setattr(bd, "get_active_blaxel_session_root", lambda: None)
    return bd


def test_to_sandbox_relative_file(dispatch) -> None:
    assert dispatch._to_sandbox_path("code.txt") == "/tmp/code.txt"


def test_to_sandbox_empty_is_root(dispatch) -> None:
    assert dispatch._to_sandbox_path("") == "/tmp"


def test_to_sandbox_traversal_collapses_to_basename(dispatch) -> None:
    out = dispatch._to_sandbox_path("a/../../../etc/passwd")
    assert out == "/tmp/passwd"


def test_sandbox_root_default_tmp(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.tools.blaxel_dispatch as bd

    monkeypatch.setattr(bd, "settings", SimpleNamespace(blaxel_sandbox_workdir=""))
    monkeypatch.setattr(bd, "get_active_blaxel_session_root", lambda: None)
    assert bd._sandbox_root_posix() == "/tmp"


def test_sandbox_root_prefers_session_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.tools.blaxel_dispatch as bd

    monkeypatch.setattr(bd, "settings", SimpleNamespace(blaxel_sandbox_workdir="/tmp"))
    monkeypatch.setattr(bd, "get_active_blaxel_session_root", lambda: "/tmp/koraku/users/u1/sessions/sid")
    assert bd._to_sandbox_path("code.txt") == "/tmp/koraku/users/u1/sessions/sid/code.txt"
