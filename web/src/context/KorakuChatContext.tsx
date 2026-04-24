"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { KorakuChatApi } from "@/hooks/useKorakuChat";

const KorakuChatContext = createContext<KorakuChatApi | null>(null);

export function KorakuChatProvider({
  value,
  children,
}: {
  value: KorakuChatApi;
  children: ReactNode;
}) {
  return <KorakuChatContext.Provider value={value}>{children}</KorakuChatContext.Provider>;
}

export function useKorakuChatContext(): KorakuChatApi {
  const v = useContext(KorakuChatContext);
  if (!v) {
    throw new Error("useKorakuChatContext must be used under KorakuAppShell");
  }
  return v;
}
