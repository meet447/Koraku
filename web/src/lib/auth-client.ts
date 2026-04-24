import { createAuthClient } from "better-auth/react";

const baseURL =
  process.env.NEXT_PUBLIC_SITE_URL?.trim() ||
  process.env.NEXT_PUBLIC_APP_URL?.trim() ||
  "http://localhost:3000";

export const authClient = createAuthClient({
  baseURL,
});
