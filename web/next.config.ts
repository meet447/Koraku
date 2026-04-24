import type { NextConfig } from "next";

const backend = process.env.KORAKU_BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // /koraku-api/stream is handled by src/app/koraku-api/stream/route.ts (true streaming).
      { source: "/koraku-api/health", destination: `${backend}/health` },
      {
        source: "/koraku-api/api/chat-models",
        destination: `${backend}/api/chat-models`,
      },
      // /koraku-api/api/personalization → Route Handler (forwards Supabase Bearer from cookies)
      // /koraku-api/api/composio/* is handled by src/app/koraku-api/api/composio/[[...path]]/route.ts
      // so Authorization (Supabase Bearer token) is forwarded to Python.
      // /koraku-api/api/workspace/* is handled by src/app/koraku-api/api/workspace/[[...path]]/route.ts
      // /koraku-api/api/automations/* is handled by src/app/koraku-api/api/automations/[[...path]]/route.ts
      // so long-running POST …/run is not buffered or timed out by rewrites.
    ];
  },
};

export default nextConfig;
