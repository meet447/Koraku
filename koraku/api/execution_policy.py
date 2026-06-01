"""Chat execution_target policy: Blaxel cloud vs in-process on the API host."""
from __future__ import annotations

from fastapi import HTTPException, Request

from koraku.api.linked_device import chat_local_execution_available
from koraku.core.config import Settings


def assert_chat_local_execution_allowed(request: Request, settings: Settings) -> None:
    """Raise when ``execution_target=local`` cannot run on this API host.

  - Linked desktop pairing (future): HTTP 501 until device transport ships.
  - In-process on the machine running Koraku (OSS / self-host): allowed when
    ``allow_local_execution_in_chat`` is true — tools use the server workspace.
    """
    if chat_local_execution_available(request):
        raise HTTPException(
            status_code=501,
            detail=(
                "Routing chat to your linked Koraku desktop app is not implemented yet. "
                "Use Sandbox (Blaxel) or This computer instead."
            ),
        )
    if not settings.allow_local_execution_in_chat:
        raise HTTPException(
            status_code=503,
            detail=(
                "This computer mode is disabled on the server. Set ALLOW_LOCAL_EXECUTION_IN_CHAT=true "
                "or use Sandbox (Blaxel)."
            ),
        )
