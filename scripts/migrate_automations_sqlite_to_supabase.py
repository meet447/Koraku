#!/usr/bin/env python3
"""
One-time migration: copy rows from legacy ``.koraku/automations.db`` into Supabase ``koraku_automation`` / ``koraku_automation_run``.

Requires:
  - SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) and SUPABASE_SERVICE_ROLE_KEY in the environment
  - ``--user-id`` = Supabase ``auth.users.id`` (uuid) to own all imported rows
  - ``--sqlite-path`` = path to the SQLite file (e.g. repo/.koraku/automations.db)

Usage (from repo root):

  python scripts/migrate_automations_sqlite_to_supabase.py \\
    --sqlite-path .koraku/automations.db \\
    --user-id 00000000-0000-0000-0000-000000000000

Use ``--dry-run`` to print counts without writing.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import httpx


def _rest(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/rest/v1{path}"


def _headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sqlite-path", required=True, help="Path to automations.db")
    p.add_argument("--user-id", required=True, dest="user_id", help="Supabase auth user uuid")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    base = (os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base or not key:
        print("Set SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) and SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 1

    db_path = Path(args.sqlite_path).expanduser().resolve()
    if not db_path.is_file():
        print(f"SQLite file not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    autos = conn.execute("SELECT * FROM automations").fetchall()
    runs = conn.execute("SELECT * FROM automation_runs").fetchall()
    conn.close()

    print(f"Found {len(autos)} automations, {len(runs)} runs in {db_path}")
    if args.dry_run:
        return 0

    uid = args.user_id.strip()
    with httpx.Client(timeout=120.0) as client:
        for r in autos:
            tk = json.loads(r["toolkits_json"] or "[]")
            if not isinstance(tk, list):
                tk = []
            body = {
                "id": r["id"],
                "user_id": uid,
                "title": r["title"],
                "headline": r["headline"] or "",
                "natural_language_spec": r["natural_language_spec"],
                "trigger_mode": r["trigger_mode"],
                "status": r["status"],
                "timezone": r["timezone"],
                "cron_expression": r["cron_expression"],
                "event_display": r["event_display"],
                "toolkits": [str(x).strip().upper() for x in tk if str(x).strip()],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "last_run_at": r["last_run_at"],
                "next_run_at": r["next_run_at"],
            }
            url = _rest(base, "/koraku_automation")
            resp = client.post(url, headers=_headers(key), content=json.dumps(body))
            if resp.status_code not in (200, 201):
                print(f"Failed automation {r['id']}: {resp.status_code} {resp.text}", file=sys.stderr)
                return 1

        for r in runs:
            body = {
                "id": r["id"],
                "automation_id": r["automation_id"],
                "user_id": uid,
                "status": r["status"],
                "trigger_summary": r["trigger_summary"] or "",
                "result_summary": r["result_summary"],
                "error": r["error"],
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
                "duration_ms": r["duration_ms"],
            }
            url = _rest(base, "/koraku_automation_run")
            resp = client.post(url, headers=_headers(key), content=json.dumps(body))
            if resp.status_code not in (200, 201):
                print(f"Failed run {r['id']}: {resp.status_code} {resp.text}", file=sys.stderr)
                return 1

    print("Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
