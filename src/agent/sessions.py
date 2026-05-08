"""In-memory chat session store (shared by stream routes and health)."""
from __future__ import annotations

import uuid
from datetime import timedelta

from src.core.config import settings
from src.core.models import SessionState, as_utc, utcnow

# In-memory session store (use Redis in production)
sessions: dict[str, SessionState] = {}


def create_session(session_id: str | None = None, *, owner_sub: str | None = None) -> SessionState:
    """Create a new in-memory session bound to ``owner_sub`` (Supabase ``sub``)."""
    sid = (session_id or "").strip()
    if sid:
        sid = sid[:255]
    sid = sid or str(uuid.uuid4())
    session = SessionState(session_id=sid, owner_sub=owner_sub)
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


def get_or_create_chat_session(
    raw_session_id: str | None,
    *,
    owner_sub: str | None = None,
) -> SessionState:
    """Resume the session only when ``owner_sub`` matches; otherwise allocate a fresh one.

    The previous behavior keyed sessions by raw UUID alone — on a Supabase outage
    (when DB hydration silently no-ops), one user could resume another user's
    in-memory ``messages`` by guessing or replaying the same ``session_id``.
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
            if sess.owner_sub != owner_sub:
                # Someone else's session under this id (or stale anon entry). Drop it.
                del sessions[rs]
            elif utcnow() - as_utc(sess.updated_at) <= timedelta(hours=float(settings.session_ttl_hours)):
                sess.touch()
                return sess
            else:
                del sessions[rs]
    if rs:
        return create_session(rs, owner_sub=owner_sub)
    return create_session(owner_sub=owner_sub)
