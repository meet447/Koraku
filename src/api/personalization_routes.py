"""Personalization files API (``.koraku/`` display name + memory/soul)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.workspace.context import read_personalization_files, write_personalization_files
from src.workspace.paths import workspace_dir

router = APIRouter(prefix="/api", tags=["personalization"])


class PersonalizationUpdate(BaseModel):
    """Edits agent display name plus ``Memory.md`` / ``Soul.md`` in the server workspace."""

    agent_name: str = Field(default="", max_length=120)
    memory: str = Field(default="", max_length=600_000)
    soul: str = Field(default="", max_length=600_000)


@router.get("/personalization")
async def personalization_get():
    """Load personalization from ``.koraku/`` under the process working directory."""
    ws = workspace_dir()
    return read_personalization_files(ws)


@router.put("/personalization")
async def personalization_put(body: PersonalizationUpdate):
    """Persist personalization files (creates ``.koraku/`` when needed)."""
    ws = workspace_dir()
    write_personalization_files(ws, body.agent_name, body.memory, body.soul)
    return {"ok": True}
