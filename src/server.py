"""FastAPI application: lifespan, static UI mount, and included API routers."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.core.config import settings
from src.agent import Agent
from src.api.automations_routes import router as automations_router
from src.api.chat_routes import router as chat_router
from src.api.composio_routes import router as composio_router
from src.api.health_routes import router as health_router
from src.api.personalization_routes import router as personalization_router
from src.api.workspace_routes import router as workspace_router
from src.automations import scheduler as automation_scheduler
from src.core.app_paths import static_assets_dir
from src.llm.catalog import any_llm_configured

if any_llm_configured():
    _default_agent: Agent | None = Agent()
    MODE = "live"
else:
    _default_agent = None
    MODE = "unconfigured"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    app.state.koraku_agent = _default_agent
    app.state.server_mode = MODE
    print(f"🚀 {settings.agent_name} v{settings.version} starting up in {MODE} mode")
    if MODE == "unconfigured":
        print("⚠️  LLM is not configured. Set API keys / base URL (see /health). SSE will return setup instructions.")
    else:
        print(f"   Provider: {settings.llm_provider}")
        if settings.llm_provider == "fireworks":
            print(f"   Model: {settings.fireworks_model}")
        elif settings.llm_provider == "anthropic":
            print(f"   Model: {settings.anthropic_model}")
        else:
            print(f"   Model: {settings.custom_model}")
    print(f"   Max steps standard: {settings.max_steps} | extended: {settings.research_max_steps}")
    if settings.exa_api_key:
        print("   ✅ ExaSearch enabled")
    if settings.firecrawl_api_key:
        print("   ✅ Firecrawl enabled")
    if settings.blaxel_cloud_sandbox_enabled:
        import sys

        from src.integrations import blaxel_runtime as _blaxel_rt

        if not _blaxel_rt.blaxel_sdk_available():
            err = _blaxel_rt.blaxel_import_error_message() or "unknown"
            print("   ⚠️  BLAXEL_CLOUD_SANDBOX_ENABLED=true but `blaxel` is not importable in this worker.")
            print(f"      sys.executable = {sys.executable}")
            print(f"      Import error: {err}")
            print(f"      Install with: {sys.executable} -m pip install blaxel")
        else:
            print("   ✅ Blaxel (cloud sandboxes)")
    automation_scheduler.configure_automation_scheduler(_default_agent)
    if _default_agent is not None:
        automation_scheduler.start_automation_scheduler()
    yield
    automation_scheduler.shutdown_automation_scheduler()
    print("👋 Shutting down")


app = FastAPI(title=settings.agent_name, version=settings.version, lifespan=lifespan)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(personalization_router)
app.include_router(composio_router)
app.include_router(automations_router)
app.include_router(workspace_router)

static_dir = static_assets_dir()
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index():
    """Serve the web UI."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "UI not found. Run from project root."}
