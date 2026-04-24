"""Entry point for the Koraku Agent server."""
import os
import sys

import uvicorn
from src.core.config import settings


def _uvicorn_workers() -> int:
    """Process count for production (Render/Railway often set ``WEB_CONCURRENCY``)."""
    raw = (os.environ.get("WEB_CONCURRENCY") or os.environ.get("UVICORN_WORKERS") or "1").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 1
    return max(1, min(n, 32))


def _uvicorn_reload() -> bool:
    if _uvicorn_workers() > 1:
        return False
    v = (os.environ.get("UVICORN_RELOAD") or "true").strip().lower()
    return v in ("1", "true", "yes", "on")


if __name__ == "__main__":
    # Helps debug “No module named 'blaxel'” when the shell shows (venv) but a different python runs.
    print(f"Koraku server Python: {sys.executable}")
    workers = _uvicorn_workers()
    reload = _uvicorn_reload()
    if workers > 1:
        print(f"Koraku server: {workers} worker processes (reload off). Use LB sticky sessions for /stream chat.")
    elif reload:
        print("Koraku server: single process + autoreload (dev). Set WEB_CONCURRENCY=4 and UVICORN_RELOAD=false for load.")
    kw: dict = {
        "host": settings.host,
        "port": settings.port,
        "log_level": "info",
    }
    if workers > 1:
        kw["workers"] = workers
    else:
        kw["reload"] = reload
    uvicorn.run("src.server:app", **kw)
