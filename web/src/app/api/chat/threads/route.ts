import { desc, eq } from "drizzle-orm";
import { headers } from "next/headers";
import { db } from "@/db";
import { chatThread } from "@/db/schema";
import { auth } from "@/lib/auth";
import {
  getCachedJson,
  invalidateUserThreadList,
  setCachedJson,
} from "@/lib/koraku-redis";

export const runtime = "nodejs";

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session?.user?.id) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  const uid = session.user.id;
  const cacheKey = `threads:${uid}`;
  const cached = await getCachedJson<
    { id: string; title: string; updatedAt: string | null }[]
  >(cacheKey);
  if (cached) {
    return Response.json({ threads: cached });
  }

  const rows = await db
    .select()
    .from(chatThread)
    .where(eq(chatThread.userId, uid))
    .orderBy(desc(chatThread.updatedAt))
    .limit(200);

  const threads = rows.map((r) => ({
    id: r.id,
    title: r.title,
    updatedAt: r.updatedAt?.toISOString() ?? null,
  }));
  await setCachedJson(cacheKey, threads, 30);
  return Response.json({ threads });
}

export async function POST(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session?.user?.id) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  let title = "New chat";
  try {
    const body = (await req.json()) as { title?: string };
    if (typeof body.title === "string" && body.title.trim()) {
      title = body.title.trim().slice(0, 200);
    }
  } catch {
    /* ignore empty body */
  }
  const id = crypto.randomUUID();
  await db.insert(chatThread).values({
    id,
    userId: session.user.id,
    title,
  });
  await invalidateUserThreadList(session.user.id);
  return Response.json({ id, title });
}
