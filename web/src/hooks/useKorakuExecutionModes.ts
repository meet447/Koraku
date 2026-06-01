"use client";

import { useEffect, useState } from "react";

export type ChatExecutionSurface = "cloud" | "local" | "server";

type HealthSnapshot = {
  cloudBlocked: boolean;
  cloudBlockReason: string | null;
  allowLocal: boolean;
  allowServer: boolean;
};

function pickDefaultMode(health: HealthSnapshot): ChatExecutionSurface {
  if (!health.cloudBlocked) return "cloud";
  if (health.allowLocal) return "local";
  if (health.allowServer) return "server";
  return "cloud";
}

function pickComputerTarget(health: HealthSnapshot): ChatExecutionSurface {
  return health.allowLocal ? "local" : "server";
}

export function useKorakuExecutionModes() {
  const [health, setHealth] = useState<HealthSnapshot>({
    cloudBlocked: true,
    cloudBlockReason: null,
    allowLocal: true,
    allowServer: true,
  });
  const [executionTarget, setExecutionTarget] =
    useState<ChatExecutionSurface>("local");
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
          allowLocal: data.allow_local_execution_in_chat !== false,
          allowServer: data.allow_server_execution_in_chat !== false,
        };
        if (!cancelled) {
          setHealth(snap);
          setExecutionTarget(pickDefaultMode(snap));
          setReady(true);
        }
      } catch {
        if (!cancelled) {
          const snap: HealthSnapshot = {
            cloudBlocked: true,
            cloudBlockReason: null,
            allowLocal: true,
            allowServer: true,
          };
          setHealth(snap);
          setExecutionTarget("local");
          setReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const showCloud = !health.cloudBlocked;
  const showComputer = health.allowLocal || health.allowServer;
  const computerTarget = pickComputerTarget(health);

  return {
    ready,
    executionTarget,
    setExecutionTarget,
    showCloud,
    showComputer,
    computerTarget,
    cloudBlockReason: health.cloudBlockReason,
  };
}
