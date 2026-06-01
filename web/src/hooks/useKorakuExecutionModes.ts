"use client";

import { useEffect, useState } from "react";

export type ChatExecutionSurface = "cloud" | "local" | "server";

type HealthSnapshot = {
  cloudBlocked: boolean;
  cloudBlockReason: string | null;
};

const LOCAL_ENABLED =
  process.env.NEXT_PUBLIC_KORAKU_LOCAL_EXECUTION === "1" ||
  process.env.NEXT_PUBLIC_KORAKU_LOCAL_EXECUTION === "true";

function pickDefaultMode(health: HealthSnapshot): ChatExecutionSurface {
  if (health.cloudBlocked) return "server";
  return "cloud";
}

export function useKorakuExecutionModes() {
  const [health, setHealth] = useState<HealthSnapshot>({
    cloudBlocked: true,
    cloudBlockReason: null,
  });
  const [executionTarget, setExecutionTarget] =
    useState<ChatExecutionSurface>("server");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/koraku-api/health", { cache: "no-store" });
        if (!r.ok) throw new Error(String(r.status));
        const data = (await r.json()) as Record<string, unknown>;
        const reason = data.cloud_chat_sandbox_block_reason;
        const snap: HealthSnapshot = {
          cloudBlocked: typeof reason === "string" && reason.length > 0,
          cloudBlockReason: typeof reason === "string" ? reason : null,
        };
        if (!cancelled) {
          setHealth(snap);
          setExecutionTarget(pickDefaultMode(snap));
          setReady(true);
        }
      } catch {
        if (!cancelled) {
          setHealth({ cloudBlocked: true, cloudBlockReason: null });
          setExecutionTarget("server");
          setReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const showCloud = !health.cloudBlocked;
  const showLocal = LOCAL_ENABLED && showCloud;
  const showServer = health.cloudBlocked || !showCloud;

  return {
    ready,
    executionTarget,
    setExecutionTarget,
    showCloud,
    showLocal,
    showServer,
    cloudBlockReason: health.cloudBlockReason,
  };
}
