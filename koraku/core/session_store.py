"""Pluggable chat session storage (memory or Upstash Redis)."""
from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any

import httpx

from koraku.core.config import get_settings, settings
from koraku.core.models import SessionState, as_utc, utcnow

log = logging.getLogger(__name__)

SessionStoreBackend = str  # "memory" | "redis"


class SessionStore(ABC):
    @abstractmethod
    def get(self, session_id: str) -> SessionState | None: ...

    @abstractmethod
    def save(self, session: SessionState) -> None: ...

    @abstractmethod
    def delete(self, session_id: str) -> None: ...

    @abstractmethod
    def count(self) -> int: ...

    def prune(self) -> None:
        """Optional maintenance hook (memory store evicts idle sessions)."""

    def get_or_create(
        self,
        raw_session_id: str | None,
        *,
        owner_sub: str | None = None,
    ) -> SessionState:
        self.prune()
        rs = (raw_session_id or "").strip()
        if rs:
            rs = rs[:255]
            try:
                uuid.UUID(rs)
            except ValueError:
                rs = ""
            if rs:
                existing = self.get(rs)
                if existing is not None:
                    if existing.owner_sub != owner_sub:
                        self.delete(rs)
                    elif utcnow() - as_utc(existing.updated_at) <= timedelta(
                        hours=float(settings.session_ttl_hours)
                    ):
                        existing.touch()
                        self.save(existing)
                        return existing
                    else:
                        self.delete(rs)
                return self._create(rs, owner_sub=owner_sub)
        return self._create(owner_sub=owner_sub)

    def _create(self, session_id: str | None = None, *, owner_sub: str | None = None) -> SessionState:
        sid = (session_id or "").strip()
        if sid:
            sid = sid[:255]
        sid = sid or str(uuid.uuid4())
        session = SessionState(session_id=sid, owner_sub=owner_sub)
        self.save(session)
        return session


class MemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self.sessions: dict[str, SessionState] = {}

    def get(self, session_id: str) -> SessionState | None:
        return self.sessions.get(session_id)

    def save(self, session: SessionState) -> None:
        self.sessions[session.session_id] = session

    def delete(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    def count(self) -> int:
        return len(self.sessions)

    def prune(self) -> None:
        now = utcnow()
        ttl = timedelta(hours=float(settings.session_ttl_hours))
        for sid in list(self.sessions.keys()):
            s = self.sessions.get(sid)
            if s is None:
                continue
            if now - as_utc(s.updated_at) > ttl:
                del self.sessions[sid]
        max_n = int(settings.session_store_max)
        while len(self.sessions) > max_n:
            oldest = min(self.sessions.keys(), key=lambda k: as_utc(self.sessions[k].updated_at))
            del self.sessions[oldest]


class RedisSessionStore(SessionStore):
    """Upstash Redis REST session store for multi-worker chat continuity."""

    def __init__(self) -> None:
        self._prefix = "koraku:session:"

    def _ttl_seconds(self) -> int:
        return max(60, int(float(settings.session_ttl_hours) * 3600))

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    def _rest_base(self) -> str | None:
        url = (settings.upstash_redis_rest_url or "").strip().rstrip("/")
        token = (settings.upstash_redis_rest_token or "").strip()
        if not url or not token:
            return None
        return url

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {(settings.upstash_redis_rest_token or '').strip()}",
            "Content-Type": "application/json",
        }

    def _command(self, *args: str) -> Any | None:
        base = self._rest_base()
        if not base:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(f"{base}/pipeline", headers=self._headers(), json=[args])
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning("Redis session store command failed: %s", e)
            return None
        if not isinstance(data, list) or not data:
            return None
        entry = data[0]
        if isinstance(entry, dict) and entry.get("error"):
            log.warning("Redis session store error: %s", entry.get("error"))
            return None
        return entry.get("result") if isinstance(entry, dict) else entry

    def get(self, session_id: str) -> SessionState | None:
        raw = self._command("GET", self._key(session_id))
        if not raw:
            return None
        try:
            payload = json.loads(str(raw))
            return SessionState.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as e:
            log.warning("Invalid session payload for %s: %s", session_id, e)
            self.delete(session_id)
            return None

    def save(self, session: SessionState) -> None:
        payload = session.model_dump(mode="json")
        encoded = json.dumps(payload, ensure_ascii=False)
        key = self._key(session.session_id)
        ttl = self._ttl_seconds()
        result = self._command("SET", key, encoded, "EX", str(ttl))
        if result is None:
            log.warning("Failed to persist session %s to Redis", session.session_id)

    def delete(self, session_id: str) -> None:
        self._command("DEL", self._key(session_id))

    def count(self) -> int:
        # Approximate health metric only; KEYS is expensive on large datasets.
        return -1

    def prune(self) -> None:
        return


_store: SessionStore | None = None


def build_session_store(backend: SessionStoreBackend | None = None) -> SessionStore:
    name = (backend or settings.session_store_backend or "memory").strip().lower()
    if name == "redis":
        if not (settings.upstash_redis_rest_url or "").strip() or not (
            settings.upstash_redis_rest_token or ""
        ).strip():
            log.warning(
                "session_store_backend=redis but Upstash credentials missing; falling back to memory"
            )
            return MemorySessionStore()
        return RedisSessionStore()
    return MemorySessionStore()


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = build_session_store()
    return _store


def reset_session_store() -> None:
    global _store
    _store = None


def active_session_count() -> int:
    store = get_session_store()
    n = store.count()
    if n >= 0:
        return n
    if isinstance(store, MemorySessionStore):
        return len(store.sessions)
    return 0
