"""SQLite persistence for Koraku automations and run history (under ``.koraku/automations.db``)."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

_UTC = timezone.utc


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    return dt.astimezone(_UTC).isoformat()


def db_path(workspace: str) -> Path:
    root = Path(workspace).resolve() / ".koraku"
    root.mkdir(parents=True, exist_ok=True)
    return root / "automations.db"


_lock = threading.Lock()


def _connect(workspace: str) -> sqlite3.Connection:
    path = db_path(workspace)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(workspace: str) -> None:
    with _lock:
        conn = _connect(workspace)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS automations (
                  id TEXT PRIMARY KEY,
                  title TEXT NOT NULL,
                  headline TEXT NOT NULL DEFAULT '',
                  natural_language_spec TEXT NOT NULL,
                  trigger_mode TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'active',
                  timezone TEXT,
                  cron_expression TEXT,
                  event_display TEXT,
                  toolkits_json TEXT NOT NULL DEFAULT '[]',
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  last_run_at TEXT,
                  next_run_at TEXT
                );
                CREATE TABLE IF NOT EXISTS automation_runs (
                  id TEXT PRIMARY KEY,
                  automation_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  trigger_summary TEXT NOT NULL DEFAULT '',
                  result_summary TEXT,
                  error TEXT,
                  started_at TEXT NOT NULL,
                  finished_at TEXT,
                  duration_ms INTEGER,
                  FOREIGN KEY (automation_id) REFERENCES automations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_runs_auto_started
                  ON automation_runs (automation_id, started_at DESC);
                """
            )
        finally:
            conn.close()


TriggerMode = Literal["scheduled", "event"]
AutomationStatus = Literal["active", "paused"]


def _row_to_automation(r: sqlite3.Row) -> dict[str, Any]:
    try:
        toolkits = json.loads(r["toolkits_json"] or "[]")
    except json.JSONDecodeError:
        toolkits = []
    if not isinstance(toolkits, list):
        toolkits = []
    return {
        "id": r["id"],
        "title": r["title"],
        "headline": r["headline"] or r["title"],
        "natural_language_spec": r["natural_language_spec"],
        "trigger_mode": r["trigger_mode"],
        "status": r["status"],
        "timezone": r["timezone"],
        "cron_expression": r["cron_expression"],
        "event_display": r["event_display"],
        "toolkits": [str(x).upper() for x in toolkits],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "last_run_at": r["last_run_at"],
        "next_run_at": r["next_run_at"],
    }


def list_automations(workspace: str) -> list[dict[str, Any]]:
    init_db(workspace)
    with _lock:
        conn = _connect(workspace)
        try:
            cur = conn.execute(
                "SELECT * FROM automations ORDER BY updated_at DESC"
            )
            return [_row_to_automation(r) for r in cur.fetchall()]
        finally:
            conn.close()


def get_automation(workspace: str, automation_id: str) -> dict[str, Any] | None:
    init_db(workspace)
    with _lock:
        conn = _connect(workspace)
        try:
            cur = conn.execute("SELECT * FROM automations WHERE id = ?", (automation_id,))
            r = cur.fetchone()
            return _row_to_automation(r) if r else None
        finally:
            conn.close()


def insert_automation(
    workspace: str,
    *,
    title: str,
    headline: str,
    natural_language_spec: str,
    trigger_mode: TriggerMode,
    status: AutomationStatus,
    timezone: str | None,
    cron_expression: str | None,
    event_display: str | None,
    toolkits: list[str],
) -> dict[str, Any]:
    init_db(workspace)
    aid = str(uuid.uuid4())
    now = _iso(datetime.now(_UTC))
    tk_json = json.dumps([t.strip().upper() for t in toolkits if t.strip()])
    with _lock:
        conn = _connect(workspace)
        try:
            conn.execute(
                """
                INSERT INTO automations (
                  id, title, headline, natural_language_spec, trigger_mode, status,
                  timezone, cron_expression, event_display, toolkits_json,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    aid,
                    title.strip(),
                    headline.strip() or title.strip(),
                    natural_language_spec.strip(),
                    trigger_mode,
                    status,
                    timezone,
                    cron_expression,
                    event_display,
                    tk_json,
                    now,
                    now,
                ),
            )
        finally:
            conn.close()
    row = get_automation(workspace, aid)
    assert row is not None
    return row


def update_automation(
    workspace: str,
    automation_id: str,
    *,
    title: str | None = None,
    headline: str | None = None,
    natural_language_spec: str | None = None,
    status: AutomationStatus | None = None,
    timezone: str | None = None,
    cron_expression: str | None = None,
    event_display: str | None = None,
    toolkits: list[str] | None = None,
) -> dict[str, Any] | None:
    init_db(workspace)
    fields: list[str] = []
    vals: list[Any] = []
    if title is not None:
        fields.append("title = ?")
        vals.append(title.strip())
    if headline is not None:
        fields.append("headline = ?")
        vals.append(headline.strip())
    if natural_language_spec is not None:
        fields.append("natural_language_spec = ?")
        vals.append(natural_language_spec.strip())
    if status is not None:
        fields.append("status = ?")
        vals.append(status)
    if timezone is not None:
        fields.append("timezone = ?")
        vals.append(timezone)
    if cron_expression is not None:
        fields.append("cron_expression = ?")
        vals.append(cron_expression)
    if event_display is not None:
        fields.append("event_display = ?")
        vals.append(event_display)
    if toolkits is not None:
        fields.append("toolkits_json = ?")
        vals.append(json.dumps([t.strip().upper() for t in toolkits if t.strip()]))
    if not fields:
        return get_automation(workspace, automation_id)
    now = _iso(datetime.now(_UTC))
    fields.append("updated_at = ?")
    vals.append(now)
    vals.append(automation_id)
    with _lock:
        conn = _connect(workspace)
        try:
            conn.execute(
                f"UPDATE automations SET {', '.join(fields)} WHERE id = ?",
                vals,
            )
        finally:
            conn.close()
    return get_automation(workspace, automation_id)


def delete_automation(workspace: str, automation_id: str) -> bool:
    init_db(workspace)
    with _lock:
        conn = _connect(workspace)
        try:
            cur = conn.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
            return cur.rowcount > 0
        finally:
            conn.close()


def set_automation_run_times(
    workspace: str,
    automation_id: str,
    *,
    last_run_at: datetime | None = None,
    next_run_at: datetime | None = None,
) -> None:
    init_db(workspace)
    parts: list[str] = []
    vals: list[Any] = []
    if last_run_at is not None:
        parts.append("last_run_at = ?")
        vals.append(_iso(last_run_at))
    if next_run_at is not None:
        parts.append("next_run_at = ?")
        vals.append(_iso(next_run_at))
    if not parts:
        return
    parts.append("updated_at = ?")
    vals.append(_iso(datetime.now(_UTC)))
    vals.append(automation_id)
    with _lock:
        conn = _connect(workspace)
        try:
            conn.execute(
                f"UPDATE automations SET {', '.join(parts)} WHERE id = ?",
                vals,
            )
        finally:
            conn.close()


def insert_run_start(
    workspace: str,
    automation_id: str,
    *,
    trigger_summary: str,
) -> str:
    init_db(workspace)
    rid = str(uuid.uuid4())
    now = _iso(datetime.now(_UTC))
    with _lock:
        conn = _connect(workspace)
        try:
            conn.execute(
                """
                INSERT INTO automation_runs (
                  id, automation_id, status, trigger_summary, started_at
                ) VALUES (?, ?, 'running', ?, ?)
                """,
                (rid, automation_id, trigger_summary[:8000], now),
            )
        finally:
            conn.close()
    return rid


def finish_run(
    workspace: str,
    run_id: str,
    *,
    status: Literal["success", "failed"],
    result_summary: str | None,
    error: str | None,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    with _lock:
        conn = _connect(workspace)
        try:
            conn.execute(
                """
                UPDATE automation_runs SET
                  status = ?,
                  result_summary = ?,
                  error = ?,
                  finished_at = ?,
                  duration_ms = ?
                WHERE id = ?
                """,
                (
                    status,
                    (result_summary or "")[:12000] or None,
                    (error or "")[:8000] or None,
                    _iso(finished_at),
                    duration_ms,
                    run_id,
                ),
            )
        finally:
            conn.close()


def list_runs(workspace: str, automation_id: str, limit: int = 50) -> list[dict[str, Any]]:
    init_db(workspace)
    lim = max(1, min(int(limit), 200))
    with _lock:
        conn = _connect(workspace)
        try:
            cur = conn.execute(
                """
                SELECT id, automation_id, status, trigger_summary, result_summary, error,
                       started_at, finished_at, duration_ms
                FROM automation_runs
                WHERE automation_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (automation_id, lim),
            )
            out: list[dict[str, Any]] = []
            for r in cur.fetchall():
                out.append({
                    "id": r["id"],
                    "automation_id": r["automation_id"],
                    "status": r["status"],
                    "trigger_summary": r["trigger_summary"] or "",
                    "result_summary": r["result_summary"],
                    "error": r["error"],
                    "started_at": r["started_at"],
                    "finished_at": r["finished_at"],
                    "duration_ms": r["duration_ms"],
                })
            return out
        finally:
            conn.close()


def compute_next_cron_fire(cron_expression: str, tz_name: str, base: datetime | None = None) -> datetime | None:
    """Return next UTC datetime after ``base`` for a 5-field cron in ``tz_name``."""
    try:
        from zoneinfo import ZoneInfo

        from croniter import croniter
    except ImportError:
        return None
    try:
        tz = ZoneInfo(tz_name.strip())
    except Exception:
        return None
    try:
        local_base = (base or datetime.now(_UTC)).astimezone(tz)
        it = croniter(cron_expression.strip(), local_base)
        nxt = it.get_next(datetime)
        if nxt.tzinfo is None:
            nxt = nxt.replace(tzinfo=tz)
        return nxt.astimezone(_UTC)
    except Exception:
        return None
