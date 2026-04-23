"""Entry point for the Koraku Agent server."""
import uvicorn
from src.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.server:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )
