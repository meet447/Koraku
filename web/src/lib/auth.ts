import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { nextCookies } from "better-auth/next-js";
import { redisStorage } from "@better-auth/redis-storage";
import { Redis } from "ioredis";
import { getDb } from "@/db";
import * as schema from "@/db/schema";

function buildSecondaryStorage() {
  const url = process.env.REDIS_URL?.trim();
  if (!url) return undefined;
  const client = new Redis(url, { maxRetriesPerRequest: 20 });
  return redisStorage({ client, keyPrefix: "koraku:auth:" });
}

const secondaryStorage = buildSecondaryStorage();

const baseURL =
  process.env.BETTER_AUTH_URL?.trim() ||
  process.env.NEXT_PUBLIC_APP_URL?.trim() ||
  process.env.NEXT_PUBLIC_SITE_URL?.trim() ||
  "http://localhost:3000";

const trusted = [
  baseURL,
  process.env.NEXT_PUBLIC_SITE_URL?.trim(),
  process.env.NEXT_PUBLIC_APP_URL?.trim(),
].filter((x): x is string => Boolean(x));

export const auth = betterAuth({
  secret: process.env.BETTER_AUTH_SECRET,
  baseURL,
  database: drizzleAdapter(getDb(), {
    provider: "pg",
    schema: {
      user: schema.user,
      session: schema.session,
      account: schema.account,
      verification: schema.verification,
    },
    camelCase: true,
  }),
  emailAndPassword: { enabled: true },
  trustedOrigins: trusted,
  plugins: [nextCookies()],
  ...(secondaryStorage ? { secondaryStorage } : {}),
});
