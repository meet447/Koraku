import { and, asc, eq } from "drizzle-orm";
import { headers } from "next/headers";
import { db } from "@/db";
import { chatMessage, chatThread } from "@/db/schema";
import { auth } from "@/lib/auth";
import { invalidateUserThreadList } from "@/lib/koraku-redis";

export const runtime = "nodejs";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ threadId: string }> },
) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session?.user?.id) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { threadId } = await ctx.params;
  const [thread] = await db
    .select()
    .from(chatThread)
    .where(
      and(eq(chatThread.id, threadId), eq(chatThread.userId, session.user.id)),
    )
    .limit(1);
  if (!thread) {
    return Response.json({ error: "Not found" }, { status: 404 });
  }

  const messages = await db
    .select()
    .from(chatMessage)
    .where(eq(chatMessage.threadId, threadId))
    .orderBy(asc(chatMessage.createdAt));

  return Response.json({
    messages: messages.map((m) => ({
      id: m.id,
      role: m.role,
      contentJson: m.contentJson,
      createdAt: m.createdAt?.toISOString() ?? null,
    })),
  });
}

export async function POST(
  req: Request,
  ctx: { params: Promise<{ threadId: string }> },
) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session?.user?.id) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { threadId } = await ctx.params;
  const [thread] = await db
    .select()
    .from(chatThread)
    .where(
      and(eq(chatThread.id, threadId), eq(chatThread.userId, session.user.id)),
    )
    .limit(1);
  if (!thread) {
    return Response.json({ error: "Not found" }, { status: 404 });
  }

  const body = (await req.json()) as {
    messages?: Array<{ id: string; role: string; contentJson: unknown }>;
  };
  const list = body.messages;
  if (!Array.isArray(list) || list.length === 0) {
    return Response.json({ error: "messages required" }, { status: 400 });
  }

  await db.delete(chatMessage).where(eq(chatMessage.threadId, threadId));
  await db.insert(chatMessage).values(
    list.map((m) => ({
      id: m.id,
      threadId,
      role: m.role,
      contentJson: m.contentJson as object,
    })),
  );
  await db
    .update(chatThread)
    .set({ updatedAt: new Date() })
    .where(eq(chatThread.id, threadId));
  await invalidateUserThreadList(session.user.id);
  return Response.json({ ok: true });
}
