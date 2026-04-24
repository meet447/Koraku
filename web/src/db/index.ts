import { neon } from "@neondatabase/serverless";
import { drizzle } from "drizzle-orm/neon-http";
import * as schema from "./schema";

function requireDatabaseUrl(): string {
  const url = process.env.DATABASE_URL?.trim();
  if (!url) {
    throw new Error(
      "DATABASE_URL is not set. Add your Neon connection string to .env.local",
    );
  }
  return url;
}

const globalForDb = globalThis as unknown as {
  __korakuDb?: ReturnType<typeof drizzle<typeof schema>>;
};

export function getDb() {
  if (globalForDb.__korakuDb) return globalForDb.__korakuDb;
  const sql = neon(requireDatabaseUrl());
  const db = drizzle(sql, { schema });
  if (process.env.NODE_ENV !== "development") {
    globalForDb.__korakuDb = db;
  }
  return db;
}

/** Use in API routes / server actions (throws if DATABASE_URL missing). */
export const db = new Proxy({} as ReturnType<typeof drizzle<typeof schema>>, {
  get(_target, prop, receiver) {
    return Reflect.get(getDb(), prop, receiver);
  },
});
