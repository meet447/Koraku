"""Backward compatibility: ``import src`` / ``import src.*`` redirect to ``koraku``."""
from __future__ import annotations

import importlib
import importlib.util
import sys
import warnings
from importlib.abc import MetaPathFinder

import koraku

warnings.warn(
    "The `src` package is deprecated; use `koraku` instead (pip install -e .).",
    DeprecationWarning,
    stacklevel=2,
)

from koraku import *  # noqa: F403

__all__ = koraku.__all__
__path__ = []  # PEP 420 namespace-style package for submodule redirects


class _SrcRedirectFinder(MetaPathFinder):
    """Resolve ``src.agent`` → ``koraku.agent`` (and other submodules) during migration."""

    def find_spec(self, fullname: str, path, target=None):  # type: ignore[no-untyped-def]
        if fullname == "src":
            return None
        if fullname.startswith("src."):
            return importlib.util.find_spec("koraku" + fullname[3:])
        return None


if not any(type(f).__name__ == "_SrcRedirectFinder" for f in sys.meta_path):
    sys.meta_path.insert(0, _SrcRedirectFinder())
