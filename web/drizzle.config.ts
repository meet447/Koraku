import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { config } from "dotenv";
import { defineConfig } from "drizzle-kit";

const root = __dirname;
for (const name of [".env.local", ".env"]) {
  const p = resolve(root, name);
  if (existsSync(p)) {
    config({ path: p });
  }
}

const DRIZZLE_DNS_CACHE_TTL_MS = 15 * 60 * 1000;

/**
 * Neon pooler hosts are `{id}-pooler.{region}.aws.neon.tech`.
 * A common mistake inserts a zone segment: `…-pooler.c-5.us-east-1…` → DNS ENOTFOUND.
 * Strip `c-<digits>.` only when it sits right after `-pooler.`.
 */
function repairNeonPoolerHostname(host: string): string {
  return host.replace(/(-pooler)\.c-\d+\./, "$1.");
}

/**
 * Neon dashboard URLs often include `channel_binding=require` (libpq-oriented).
 * node-pg can mis-handle that with some servers; drop it for CLI/schema tooling only.
 */
function postgresUrlForDrizzleKit(raw: string): string {
  const s = raw.trim();
  if (!s) return s;
  try {
    const u = new URL(s);
    u.hostname = repairNeonPoolerHostname(u.hostname);
    u.searchParams.delete("channel_binding");
    return u.href;
  } catch {
    return s;
  }
}

function resolveDrizzleDatabaseUrl(): string {
  const raw =
    process.env.DRIZZLE_DATABASE_URL?.trim() ||
    process.env.DATABASE_URL?.trim();
  if (!raw) {
    throw new Error(
      "Set DATABASE_URL in web/.env.local (or DRIZZLE_DATABASE_URL for Drizzle Kit only).",
    );
  }
  return postgresUrlForDrizzleKit(raw);
}

type DrizzleDnsCache = { hostname: string; hostaddr: string; at: number };

function readDrizzleDnsCache(hostname: string): DrizzleDnsCache | null {
  const p = resolve(root, ".drizzle-dns-cache.json");
  if (!existsSync(p)) return null;
  try {
    const j = JSON.parse(readFileSync(p, "utf8")) as DrizzleDnsCache;
    if (j.hostname !== hostname) return null;
    if (Date.now() - j.at > DRIZZLE_DNS_CACHE_TTL_MS) return null;
    if (!j.hostaddr) return null;
    return j;
  } catch {
    return null;
  }
}

const url = resolveDrizzleDatabaseUrl();
const parsed = new URL(url);
const dnsCache = readDrizzleDnsCache(parsed.hostname);

const dbCredentials = dnsCache
  ? {
      host: dnsCache.hostaddr,
      port: Number(parsed.port || 5432),
      user: decodeURIComponent(parsed.username),
      password: decodeURIComponent(parsed.password),
      database: parsed.pathname.replace(/^\//, "") || "postgres",
      ssl: {
        rejectUnauthorized: true as const,
        servername: parsed.hostname,
      },
    }
  : { url };

export default defineConfig({
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  verbose: process.env.DRIZZLE_VERBOSE === "1",
  dbCredentials,
});
