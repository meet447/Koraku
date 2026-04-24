import { Redis as UpstashRedis } from "@upstash/redis";
import { Redis as IoRedis } from "ioredis";

type RedisBackend = "upstash" | "ioredis" | "none";

let _backend: RedisBackend | undefined;
let _upstash: UpstashRedis | null = null;
let _ioredis: IoRedis | null = null;

/**
 * Prefer Upstash REST (UPSTASH_*) on serverless; fall back to TCP ``REDIS_URL`` + ioredis.
 * Upstash: set ``UPSTASH_REDIS_REST_URL`` and ``UPSTASH_REDIS_REST_TOKEN`` (see Upstash console).
 */
function resolveBackend(): RedisBackend {
  if (_backend !== undefined) {
    return _backend;
  }
  const restUrl = process.env.UPSTASH_REDIS_REST_URL?.trim();
  const restToken = process.env.UPSTASH_REDIS_REST_TOKEN?.trim();
  if (restUrl && restToken) {
    _upstash = new UpstashRedis({ url: restUrl, token: restToken });
    _backend = "upstash";
    return _backend;
  }
  const url = process.env.REDIS_URL?.trim();
  if (url) {
    _ioredis = new IoRedis(url, { maxRetriesPerRequest: 20 });
    _backend = "ioredis";
    return _backend;
  }
  _backend = "none";
  return _backend;
}

export async function getCachedJson<T>(key: string): Promise<T | null> {
  const b = resolveBackend();
  if (b === "upstash" && _upstash) {
    const raw = await _upstash.get(key);
    if (raw == null) return null;
    const s = typeof raw === "string" ? raw : JSON.stringify(raw);
    try {
      return JSON.parse(s) as T;
    } catch {
      return null;
    }
  }
  if (b === "ioredis" && _ioredis) {
    const raw = await _ioredis.get(key);
    if (raw == null) return null;
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }
  return null;
}

export async function setCachedJson(
  key: string,
  value: unknown,
  ttlSec: number,
): Promise<void> {
  const b = resolveBackend();
  const payload = JSON.stringify(value);
  if (b === "upstash" && _upstash) {
    await _upstash.set(key, payload, { ex: ttlSec });
    return;
  }
  if (b === "ioredis" && _ioredis) {
    await _ioredis.set(key, payload, "EX", ttlSec);
  }
}

export async function invalidateUserThreadList(userId: string): Promise<void> {
  const b = resolveBackend();
  const key = `threads:${userId}`;
  if (b === "upstash" && _upstash) {
    await _upstash.del(key);
    return;
  }
  if (b === "ioredis" && _ioredis) {
    await _ioredis.del(key);
  }
}
