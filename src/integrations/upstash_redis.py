"""Upstash Redis REST client (shared with Next.js env names)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from src.core.config import settings

log = logging.getLogger(__name__)

_DETACHED_PREFIX = "koraku:detached"


def upstash_redis_configured() -> bool:
    u = (settings.upstash_redis_rest_url or "").strip()
    t = (settings.upstash_redis_rest_token or "").strip()
    return bool(u and t)


async def upstash_execute(command: list[Any]) -> Any:
    """Run one Redis command via Upstash REST (see https://upstash.com/docs/redis/features/restapi)."""
    url = (settings.upstash_redis_rest_url or "").strip().rstrip("/")
    token = (settings.upstash_redis_rest_token or "").strip()
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=command,
        )
        r.raise_for_status()
        data = r.json()
    if isinstance(data, dict) and "result" in data:
        return data["result"]
    return data


def detached_meta_key(run_id: str) -> str:
    return f"{_DETACHED_PREFIX}:{run_id}:meta"


def detached_events_key(run_id: str) -> str:
    return f"{_DETACHED_PREFIX}:{run_id}:events"


def detached_seq_key(run_id: str) -> str:
    return f"{_DETACHED_PREFIX}:{run_id}:seq"


async def detached_run_create(run_id: str, owner_sub: str | None) -> None:
    meta = json.dumps({"owner_sub": owner_sub, "done": False})
    ttl = 900
    mk, ek, sk = detached_meta_key(run_id), detached_events_key(run_id), detached_seq_key(run_id)
    await upstash_execute(["SET", mk, meta, "EX", str(ttl)])
    await upstash_execute(["DEL", ek])
    await upstash_execute(["SET", sk, "-1", "EX", str(ttl)])


async def detached_run_exists(run_id: str) -> bool:
    mk = detached_meta_key(run_id)
    v = await upstash_execute(["EXISTS", mk])
    try:
        return int(v) == 1
    except (TypeError, ValueError):
        return False


async def detached_run_allows(run_id: str, auth_sub: str | None) -> bool:
    mk = detached_meta_key(run_id)
    raw = await upstash_execute(["GET", mk])
    if not raw or not isinstance(raw, str):
        return False
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        return False
    owner = meta.get("owner_sub")
    if owner is None or owner == "":
        return True
    return auth_sub == owner


async def detached_run_owner_sub(run_id: str) -> str | None:
    """Non-empty owner ``sub`` if the run is scoped to a signed-in user, else ``None``."""
    mk = detached_meta_key(run_id)
    raw = await upstash_execute(["GET", mk])
    if not raw or not isinstance(raw, str):
        return None
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        return None
    o = meta.get("owner_sub")
    if o is None or o == "":
        return None
    return str(o)


async def detached_run_append_chunk(run_id: str, raw_chunk: str) -> None:
    """Append one SSE block; assigns monotonic ``id:`` line like the in-memory buffer."""
    mk = detached_meta_key(run_id)
    raw_meta = await upstash_execute(["GET", mk])
    if not raw_meta or not isinstance(raw_meta, str):
        return
    try:
        if bool(json.loads(raw_meta).get("done")):
            return
    except json.JSONDecodeError:
        return

    ek, sk = detached_events_key(run_id), detached_seq_key(run_id)
    seq = int(await upstash_execute(["INCR", sk]))
    wrapped = raw_chunk if raw_chunk.startswith("id: ") else f"id: {seq}\n{raw_chunk}"
    ttl = 900
    payload = json.dumps({"seq": seq, "chunk": wrapped})
    await upstash_execute(["RPUSH", ek, payload])
    for k in (ek, sk, mk):
        await upstash_execute(["EXPIRE", k, str(ttl)])


async def detached_run_finish(run_id: str) -> None:
    mk = detached_meta_key(run_id)
    raw = await upstash_execute(["GET", mk])
    if not raw or not isinstance(raw, str):
        return
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        meta = {}
    meta["done"] = True
    ttl = 900
    await upstash_execute(["SET", mk, json.dumps(meta), "EX", str(ttl)])


async def detached_run_is_done(run_id: str) -> bool:
    mk = detached_meta_key(run_id)
    raw = await upstash_execute(["GET", mk])
    if not raw or not isinstance(raw, str):
        return True
    try:
        return bool(json.loads(raw).get("done"))
    except json.JSONDecodeError:
        return True


async def detached_run_delete(run_id: str) -> None:
    mk, ek, sk = detached_meta_key(run_id), detached_events_key(run_id), detached_seq_key(run_id)
    try:
        await upstash_execute(["DEL", mk, ek, sk])
    except Exception as e:
        log.debug("detached run redis delete: %s", e)


async def detached_run_lrange_all(run_id: str) -> list[str]:
    ek = detached_events_key(run_id)
    out = await upstash_execute(["LRANGE", ek, "0", "-1"])
    if not isinstance(out, list):
        return []
    return [str(x) for x in out]


async def detached_run_llen(run_id: str) -> int:
    ek = detached_events_key(run_id)
    v = await upstash_execute(["LLEN", ek])
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


async def detached_run_lrange_slice(run_id: str, start: int, end: int) -> list[str]:
    ek = detached_events_key(run_id)
    out = await upstash_execute(["LRANGE", ek, str(start), str(end)])
    if not isinstance(out, list):
        return []
    return [str(x) for x in out]
