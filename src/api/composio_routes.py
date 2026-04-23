"""Composio integrations API (connections UI)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.integrations import composio as composio_runtime
from src.workspace.paths import workspace_dir

router = APIRouter(prefix="/api/composio", tags=["composio"])


class ComposioConnectBody(BaseModel):
    toolkit: str = Field(..., min_length=2, max_length=64)


@router.get("/overview")
async def composio_overview():
    """Connection status + active toolkits for the Connections UI."""
    composio_runtime.configure_workspace_cache(workspace_dir())
    return {
        "configured": composio_runtime.is_configured(),
        "user_id": composio_runtime.user_id() if composio_runtime.is_configured() else None,
        "connections": composio_runtime.list_connections_summary() if composio_runtime.is_configured() else [],
        "active_toolkits": composio_runtime.active_toolkit_slugs() if composio_runtime.is_configured() else [],
    }


@router.get("/toolkits")
async def composio_toolkits_search(q: str = ""):
    composio_runtime.configure_workspace_cache(workspace_dir())
    if not composio_runtime.is_configured():
        return {"items": [], "configured": False}
    return {"items": composio_runtime.search_toolkits(q), "configured": True}


@router.post("/connect")
async def composio_connect(body: ComposioConnectBody):
    composio_runtime.configure_workspace_cache(workspace_dir())
    if not composio_runtime.is_configured():
        raise HTTPException(status_code=503, detail="Set COMPOSIO_API_KEY to connect integrations.")
    try:
        return composio_runtime.start_toolkit_auth(body.toolkit.strip().upper())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
