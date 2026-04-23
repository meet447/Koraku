import type { NextRequest } from "next/server";

const backend = (process.env.KORAKU_BACKEND_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Stream POST /stream from the Koraku FastAPI backend without buffering.
 * Next.js rewrites can coalesce SSE chunks; this handler forwards `response.body` directly.
 */
export async function POST(req: NextRequest) {
  const body = await req.text();
  const upstream = await fetch(`${backend}/stream`, {
    method: "POST",
    headers: {
      "Content-Type": req.headers.get("content-type") || "application/json",
      Accept: "text/event-stream",
    },
    body,
    cache: "no-store",
    signal: req.signal,
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
