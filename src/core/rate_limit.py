"""Small in-process rate limiter for public-beta cost controls."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import DefaultDict, Deque

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class RateLimit:
    """Fixed-window-ish limiter backed by recent request timestamps."""

    key: str
    limit: int
    window_seconds: float = 60.0


_hits: DefaultDict[str, Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded.strip():
        return forwarded.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit_key(request: Request, *, scope: str, user_id: str | None) -> str:
    """Prefer user identity; fall back to IP for unauthenticated deployment mistakes."""

    principal = f"user:{user_id}" if user_id else f"ip:{_client_ip(request)}"
    return f"{scope}:{principal}"


def enforce_rate_limit(limit: RateLimit) -> None:
    """Raise 429 when a principal exceeds the configured requests per window."""

    max_hits = int(limit.limit)
    if max_hits <= 0:
        return
    now = time.monotonic()
    cutoff = now - float(limit.window_seconds)
    bucket = _hits[limit.key]
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= max_hits:
        retry = max(1, int(limit.window_seconds - (now - bucket[0]))) if bucket else int(limit.window_seconds)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before trying again.",
            headers={"Retry-After": str(retry)},
        )
    bucket.append(now)
