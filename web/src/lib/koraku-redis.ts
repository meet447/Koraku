import { Redis } from "ioredis";

let _redis: Redis | null | undefined;

function getClient(): Redis | null {
  if (_redis === undefined) {
    const url = process.env.REDIS_URL?.trim();
    _redis = url ? new Redis(url, { maxRetriesPerRequest: 20 }) : null;
  }
  return _redis;
}

export async function getCachedJson<T>(key: string): Promise<T | null> {
  const r = getClient();
  if (!r) return null;
  const raw = await r.get(key);
  if (raw == null) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function setCachedJson(
  key: string,
  value: unknown,
  ttlSec: number,
): Promise<void> {
  const r = getClient();
  if (!r) return;
  await r.set(key, JSON.stringify(value), "EX", ttlSec);
}

export async function invalidateUserThreadList(userId: string): Promise<void> {
  const r = getClient();
  if (!r) return;
  await r.del(`threads:${userId}`);
}
