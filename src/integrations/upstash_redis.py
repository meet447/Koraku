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


def _base_url() -> str:
    return (settings.upstash_redis_rest_url or "").strip().rstrip("/")


def _token() -> str:
    return (settings.upstash_redis_rest_token or "").strip()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}"}


def _http_timeout() -> httpx.Timeout:
    return httpx.Timeout(30.0, connect=10.0)


def _parse_pipeline_body(body: Any) -> list[Any]:
    if not isinstance(body, list):
        raise RuntimeError(f"unexpected Upstash pipeline response: {body!r}")
    out: list[Any] = []
    for item in body:
        if isinstance(item, dict) and item.get("error"):
            raise RuntimeError(str(item["error"]))
        if isinstance(item, dict) and "result" in item:
            out.append(item["result"])
        else:
            out.append(item)
    return out


async def upstash_execute(command: list[Any]) -> Any:
    """Run one Redis command via Upstash REST (see https://upstash.com/docs/redis/features/restapi)."""
    url = _base_url()
    token = _token()
    if not url or not token:
        raise RuntimeError("Upstash Redis is not configured.")
    async with httpx.AsyncClient(timeout=_http_timeout()) as client:
        r = await client.post(url, headers=_auth_headers(), json=command)
        r.raise_for_status()
        data = r.json()
    if isinstance(data, dict) and "result" in data:
        return data["result"]
    return data


async def upstash_pipeline(commands: list[list[Any]]) -> list[Any]:
    """Run multiple Redis commands in a single HTTP request (``POST …/pipeline``)."""
    url = _base_url()
    token = _token()
    if not url or not token:
        raise RuntimeError("Upstash Redis is not configured.")
    if not commands:
        return []
    async with httpx.AsyncClient(timeout=_http_timeout()) as client:
        r = await client.post(f"{url}/pipeline", headers=_auth_headers(), json=commands)
        r.raise_for_status()
        return _parse_pipeline_body(r.json())


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
    await upstash_pipeline(
        [
            ["SET", mk, meta, "EX", str(ttl)],
            ["DEL", ek],
            ["SET", sk, "-1", "EX", str(ttl)],
        ]
    )


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
    """Append one SSE block; assigns monotonic ``id:`` line like the in-memory buffer.

    Uses one HTTP keep-alive connection for GET + pipeline(s): previously each chunk did many
    sequential REST calls (each opening a new client), which made token streaming take minutes
    under Upstash.
    """
    url = _base_url()
    token = _token()
    if not url or not token:
        return
    mk = detached_meta_key(run_id)
    ek, sk = detached_events_key(run_id), detached_seq_key(run_id)
    ttl = 900
    headers = _auth_headers()
    async with httpx.AsyncClient(timeout=_http_timeout()) as client:
        r0 = await client.post(url, headers=headers, json=["GET", mk])
        r0.raise_for_status()
        d0 = r0.json()
        raw_meta = d0.get("result") if isinstance(d0, dict) else None
        if not raw_meta or not isinstance(raw_meta, str):
            return
        try:
            if bool(json.loads(raw_meta).get("done")):
                return
        except json.JSONDecodeError:
            return

        r1 = await client.post(f"{url}/pipeline", headers=headers, json=[["INCR", sk]])
        r1.raise_for_status()
        incr_out = _parse_pipeline_body(r1.json())
        if not incr_out:
            return
        seq = int(incr_out[0])
        wrapped = raw_chunk if raw_chunk.startswith("id: ") else f"id: {seq}\n{raw_chunk}"
        payload = json.dumps({"seq": seq, "chunk": wrapped})
        write_cmds: list[list[Any]] = [["RPUSH", ek, payload]]
        if seq == 0 or (seq % 25) == 0:
            write_cmds.extend(
                [
                    ["EXPIRE", ek, str(ttl)],
                    ["EXPIRE", sk, str(ttl)],
                    ["EXPIRE", mk, str(ttl)],
                ]
            )
        r2 = await client.post(f"{url}/pipeline", headers=headers, json=write_cmds)
        r2.raise_for_status()


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
