/**
 * When system DNS returns ENOTFOUND for *.aws.neon.tech but public DNS works (common on
 * locked-down cloud shells), resolve A records via public DNS and write a short-lived cache
 * so drizzle.config.ts can connect with host=<IP> + TLS SNI servername=<hostname>.
 */
import { existsSync, unlinkSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import dns from "node:dns";
import { config } from "dotenv";

const TTL_MS = 15 * 60 * 1000;

function repairNeonPoolerHostname(host) {
  return host.replace(/(-pooler)\.c-\d+\./, "$1.");
}

function prepareUrl(raw) {
  const s = raw.trim();
  if (!s) return null;
  try {
    const u = new URL(s);
    u.hostname = repairNeonPoolerHostname(u.hostname);
    u.searchParams.delete("channel_binding");
    return u;
  } catch {
    return null;
  }
}

async function resolveAFromGoogleDoh(hostname) {
  const url = `https://dns.google/resolve?name=${encodeURIComponent(hostname)}&type=A`;
  const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) return [];
  const data = await res.json();
  if (data.Status !== 0 || !Array.isArray(data.Answer)) return [];
  const ips = [];
  for (const a of data.Answer) {
    if (a.type === 1 && typeof a.data === "string") ips.push(a.data);
  }
  return ips;
}

/**
 * @param {string} webRoot absolute path to web/
 */
export async function preflightNeonDns(webRoot) {
  for (const name of [".env.local", ".env"]) {
    const p = path.resolve(webRoot, name);
    if (existsSync(p)) config({ path: p });
  }

  const raw =
    process.env.DRIZZLE_DATABASE_URL?.trim() ||
    process.env.DATABASE_URL?.trim();
  if (!raw) {
    throw new Error("Missing DATABASE_URL (or DRIZZLE_DATABASE_URL).");
  }

  const u = prepareUrl(raw);
  if (!u) {
    throw new Error("DATABASE_URL is not a valid URL.");
  }

  const hostname = u.hostname;
  const cachePath = path.resolve(webRoot, ".drizzle-dns-cache.json");

  let systemOk = false;
  try {
    await dns.promises.lookup(hostname);
    systemOk = true;
  } catch {
    systemOk = false;
  }

  if (systemOk) {
    if (existsSync(cachePath)) {
      try {
        unlinkSync(cachePath);
      } catch {
        /* ignore */
      }
    }
    return;
  }

  let ips = [];
  try {
    dns.setServers(["8.8.8.8", "1.1.1.1"]);
    ips = await dns.promises.resolve4(hostname);
  } catch {
    ips = [];
  }

  if (ips.length === 0) {
    try {
      ips = await resolveAFromGoogleDoh(hostname);
    } catch {
      ips = [];
    }
  }

  if (ips.length === 0) {
    throw new Error(
      `DNS could not resolve "${hostname}" via system resolver, 8.8.8.8/1.1.1.1, or Google DNS HTTPS. Copy the host from Neon Console → Connect, or fix outbound DNS.`,
    );
  }

  const payload = {
    hostname,
    hostaddr: ips[0],
    at: Date.now(),
  };
  writeFileSync(cachePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.warn(
    `[drizzle] System DNS did not resolve ${hostname}; using public DNS (${payload.hostaddr}) for this session (see .drizzle-dns-cache.json, gitignored).`,
  );
}

const webRoot = path.resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const entry = process.argv[1] && path.resolve(process.argv[1]);
const isMain = Boolean(entry && import.meta.url === pathToFileURL(entry).href);

if (isMain) {
  try {
    await preflightNeonDns(webRoot);
  } catch (e) {
    console.error(e?.message || e);
    process.exit(1);
  }
}
