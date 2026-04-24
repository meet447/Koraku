/**
 * Quick TCP check for DATABASE_URL / DRIZZLE_DATABASE_URL (same rules as Drizzle Kit).
 * Runs neon-dns-preflight so broken system DNS can fall back to public resolvers.
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dns from "node:dns/promises";
import pg from "pg";
import { preflightNeonDns } from "./neon-dns-preflight.mjs";

process.on("warning", (w) => {
  if (String(w.message).includes("SSL modes")) return;
  console.warn(w);
});

const TTL_MS = 15 * 60 * 1000;
const root = path.resolve(fileURLToPath(new URL(".", import.meta.url)), "..");

function repairNeonPoolerHostname(host) {
  return host.replace(/(-pooler)\.c-\d+\./, "$1.");
}

function preparePostgresUrlForKit(raw) {
  const s = raw.trim();
  if (!s) return { connectionString: s, hostRepair: null };
  try {
    const u = new URL(s);
    const from = u.hostname;
    const repaired = repairNeonPoolerHostname(from);
    const hostRepair =
      repaired !== from ? { from, to: repaired } : null;
    u.hostname = repaired;
    u.searchParams.delete("channel_binding");
    return { connectionString: u.href, hostRepair };
  } catch {
    return { connectionString: s, hostRepair: null };
  }
}

function readCache(hostname) {
  const p = path.resolve(root, ".drizzle-dns-cache.json");
  if (!existsSync(p)) return null;
  try {
    const j = JSON.parse(readFileSync(p, "utf8"));
    if (j.hostname !== hostname) return null;
    if (Date.now() - j.at > TTL_MS) return null;
    return j.hostaddr || null;
  } catch {
    return null;
  }
}

function printEnotfoundHelp(hostname, hostRepair) {
  console.error(`
DNS could not resolve the database host:

  ${hostname}

That name does not exist on the public internet. Common causes:
  • The connection string in web/.env.local is outdated, mistyped, or from a deleted Neon project/branch.
  • Copy a fresh string: https://console.neon.tech → your project → Connect → pick branch & role.

Expected host shape (pooled): ep-<label>-<id>-pooler.<region>.aws.neon.tech
`);
  if (hostRepair) {
    console.error(
      `Note: "${hostRepair.from}" was normalized to "${hostRepair.to}" (Neon does not use a ".c-N." segment after "-pooler").\n`,
    );
  }
}

try {
  await preflightNeonDns(root);
} catch (e) {
  console.error(e?.message || e);
  process.exit(1);
}

const raw =
  process.env.DRIZZLE_DATABASE_URL?.trim() ||
  process.env.DATABASE_URL?.trim();
if (!raw) {
  console.error(
    "Missing DATABASE_URL (or DRIZZLE_DATABASE_URL) in web/.env.local",
  );
  process.exit(1);
}

const { connectionString, hostRepair } = preparePostgresUrlForKit(raw);
if (hostRepair) {
  console.warn(
    `Repaired Neon pooler hostname (removed stray zone segment):\n  ${hostRepair.from}\n  → ${hostRepair.to}`,
  );
}

let hostname;
try {
  hostname = new URL(connectionString).hostname;
} catch {
  console.error("DATABASE_URL is not a valid URL.");
  process.exit(1);
}

const hostaddr = readCache(hostname);
if (!hostaddr) {
  try {
    await dns.lookup(hostname);
  } catch (e) {
    if (e?.code === "ENOTFOUND") {
      printEnotfoundHelp(hostname, hostRepair);
      process.exit(1);
    }
    console.error("DNS lookup failed:", e?.message || e);
    process.exit(1);
  }
}

const pool = hostaddr
  ? new pg.Pool({
      host: hostaddr,
      port: Number(new URL(connectionString).port || 5432),
      user: decodeURIComponent(new URL(connectionString).username),
      password: decodeURIComponent(new URL(connectionString).password),
      database: new URL(connectionString).pathname.replace(/^\//, "") || "postgres",
      ssl: {
        rejectUnauthorized: true,
        servername: hostname,
      },
      max: 1,
      connectionTimeoutMillis: 12_000,
    })
  : new pg.Pool({
      connectionString,
      max: 1,
      connectionTimeoutMillis: 12_000,
    });

try {
  const { rows } = await pool.query("select 1 as ok");
  console.log("Database reachable:", rows[0]);
} catch (err) {
  const msg = err?.message || String(err);
  console.error("Database connection failed:", msg);
  if (err?.code === "ENOTFOUND" || msg.includes("ENOTFOUND")) {
    printEnotfoundHelp(hostname, hostRepair);
  }
  process.exit(1);
} finally {
  await pool.end();
}
