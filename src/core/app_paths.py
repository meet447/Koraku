"""Paths for bundled assets (not the user workspace cwd)."""
from __future__ import annotations

import os


def static_assets_dir() -> str:
    """Directory containing ``index.html`` and other static UI files (repo ``static/``)."""
    # __file__ is ``src/core/app_paths.py`` → repo root is two levels up.
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "static"))
