import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { withSupabaseAuth } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  const { response, userId } = await withSupabaseAuth(request);
  const { pathname, search } = request.nextUrl;

  if (pathname.startsWith("/app") && !userId) {
    const signIn = new URL("/sign-in", request.url);
    signIn.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(signIn);
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
