"""In-memory chat session store (shared by stream routes and health)."""
from __future__ import annotations

import uuid
from datetime import timedelta

from src.core.config import settings
from src.core.models import SessionState, as_utc, utcnow

# In-memory session store (use Redis in production)
sessions: dict[str, SessionState] = {}


def create_session(session_id: str | None = None) -> SessionState:
    """Create a new in-memory session.

    When ``session_id`` is a non-empty string (typically the UI / DB thread UUID), the
    session is stored under that id so follow-up requests can resume **before** any SSE
    round-trip updates the client — fixing lost multi-turn context.
    """
    sid = (session_id or "").strip()
    if sid:
        sid = sid[:255]
    sid = sid or str(uuid.uuid4())
    session = SessionState(session_id=sid)
    sessions[sid] = session
    return session


def prune_chat_sessions() -> None:
    """Drop idle sessions past TTL; then shrink store to max size by oldest ``updated_at``."""
    now = utcnow()
    ttl = timedelta(hours=float(settings.session_ttl_hours))
    for sid in list(sessions.keys()):
        s = sessions.get(sid)
        if s is None:
            continue
        if now - as_utc(s.updated_at) > ttl:
            del sessions[sid]
    max_n = int(settings.session_store_max)
    while len(sessions) > max_n:
        oldest = min(sessions.keys(), key=lambda k: as_utc(sessions[k].updated_at))
        del sessions[oldest]


def get_or_create_chat_session(raw_session_id: str | None) -> SessionState:
    """Resume multi-turn chat when ``raw_session_id`` matches an existing non-expired session.

    If the id is a valid UUID and not yet in the store, a **new** session is created **under
    that id** (so the client's stable thread id matches the server key from the first turn).
    """
    prune_chat_sessions()
    rs = (raw_session_id or "").strip()
    if rs:
        rs = rs[:255]
        try:
            uuid.UUID(rs)
        except ValueError:
            rs = ""
        if rs and rs in sessions:
            sess = sessions[rs]
            if utcnow() - as_utc(sess.updated_at) <= timedelta(hours=float(settings.session_ttl_hours)):
                sess.touch()
                return sess
            del sessions[rs]
    if rs:
        return create_session(rs)
    return create_session()
