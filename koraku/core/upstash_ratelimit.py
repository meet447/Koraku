"""Upstash REST counter helper — keeps the rate limiter coherent across workers."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from koraku.core.config import settings

log = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(
        (settings.upstash_redis_rest_url or "").strip()
        and (settings.upstash_redis_rest_token or "").strip()
    )


def _base() -> str:
    return (settings.upstash_redis_rest_url or "").rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {(settings.upstash_redis_rest_token or '').strip()}",
        "Content-Type": "application/json",
    }


def increment_with_ttl(key: str, ttl_seconds: int) -> int | None:
    """Atomically increment ``key`` and ensure it expires ``ttl_seconds`` from creation.

    Returns the new counter value, or ``None`` if the request failed (caller should
    fall back to the in-memory limiter rather than allowing unrestricted traffic).
    """
    if not is_configured():
        return None
    url = f"{_base()}/pipeline"
    body = [
        ["INCR", key],
        ["EXPIRE", key, str(int(ttl_seconds)), "NX"],
    ]
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.post(url, json=body, headers=_headers())
            r.raise_for_status()
            data: Any = r.json()
    except httpx.HTTPError as e:
        log.warning("upstash rate-limit call failed: %s", e)
        return None
    if not isinstance(data, list) or not data:
        return None
    head = data[0]
    if isinstance(head, dict) and "result" in head:
        try:
            return int(head["result"])
        except (TypeError, ValueError):
            return None
    if isinstance(head, int):
        return head
    return None
