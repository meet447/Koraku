"""Entry point for the Koraku Agent server."""
import sys

import uvicorn
from src.core.config import settings

if __name__ == "__main__":
    # Helps debug “No module named 'blaxel'” when the shell shows (venv) but a different python runs.
    print(f"Koraku server Python: {sys.executable}")
    uvicorn.run(
        "src.server:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )
