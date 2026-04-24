import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * Protect `/app` (chat + settings). Session is validated via Better Auth’s
 * HTTP endpoint so this can stay on the Edge runtime (no direct DB in middleware).
 */
export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (!pathname.startsWith("/app")) {
    return NextResponse.next();
  }

  const origin = request.nextUrl.origin;
  const sessionRes = await fetch(`${origin}/api/auth/get-session`, {
    headers: { cookie: request.headers.get("cookie") ?? "" },
    cache: "no-store",
  });

  let body: unknown = null;
  if (sessionRes.ok) {
    try {
      body = await sessionRes.json();
    } catch {
      body = null;
    }
  }

  const ok =
    body !== null &&
    typeof body === "object" &&
    !Array.isArray(body) &&
    "user" in body &&
    (body as { user?: unknown }).user !== null &&
    typeof (body as { user?: unknown }).user === "object" &&
    !Array.isArray((body as { user: object }).user);

  if (!ok) {
    const signIn = new URL("/sign-in", request.url);
    signIn.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(signIn);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/app", "/app/:path*"],
};
