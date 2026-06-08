"""HTTP entry — Koraku SDK server (embeddable). For Cloud product use koraku_cloud.app."""
from __future__ import annotations

from koraku.server_sdk import app, create_sdk_app

__all__ = ["app", "create_sdk_app"]
