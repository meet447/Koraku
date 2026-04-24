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
      {
        source: "/koraku-api/api/personalization",
        destination: `${backend}/api/personalization`,
      },
      {
        source: "/koraku-api/api/composio/:path*",
        destination: `${backend}/api/composio/:path*`,
      },
      {
        source: "/koraku-api/api/workspace/:path*",
        destination: `${backend}/api/workspace/:path*`,
      },
      // /koraku-api/api/automations/* is handled by src/app/koraku-api/api/automations/[[...path]]/route.ts
      // so long-running POST …/run is not buffered or timed out by rewrites.
    ];
  },
};

export default nextConfig;
