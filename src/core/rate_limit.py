"""Small in-process rate limiter for public-beta cost controls."""
from __future__ import annotations

import ipaddress
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import DefaultDict, Deque

from fastapi import HTTPException, Request

from src.core.config import settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimit:
    """Fixed-window-ish limiter backed by recent request timestamps."""

    key: str
    limit: int
    window_seconds: float = 60.0


_hits: DefaultDict[str, Deque[float]] = defaultdict(deque)


def _trusted_proxy_networks() -> list[ipaddress._BaseNetwork]:
    nets: list[ipaddress._BaseNetwork] = []
    for raw in settings.trusted_proxy_cidrs_list:
        try:
            nets.append(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            log.warning("ignoring invalid TRUSTED_PROXY_CIDRS entry: %r", raw)
    return nets


def _client_ip(request: Request) -> str:
    direct = request.client.host if request.client and request.client.host else ""
    nets = _trusted_proxy_networks()
    if direct and nets:
        try:
            peer = ipaddress.ip_address(direct)
            if any(peer in n for n in nets):
                forwarded = request.headers.get("x-forwarded-for", "").strip()
                if forwarded:
                    return forwarded.split(",", 1)[0].strip()
        except ValueError:
            pass
    return direct or "unknown"


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
