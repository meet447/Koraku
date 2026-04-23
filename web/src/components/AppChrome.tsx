"use client";

import { Sidebar } from "./Sidebar";
import type { ChatSession } from "@/hooks/useKorakuChat";

export function AppChrome({
  collapsed,
  onToggleCollapse,
  sessions,
  activeId,
  streamingSessionIds = [],
  onSelectSession,
  onNewChat,
  children,
}: {
  collapsed: boolean;
  onToggleCollapse: () => void;
  sessions: ChatSession[];
  activeId: string;
  streamingSessionIds?: string[];
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-white text-koraku-ink">
      <div className="box-border flex h-full shrink-0 rounded-[28px] bg-white p-2 pr-2">
        <Sidebar
          collapsed={collapsed}
          onToggleCollapse={onToggleCollapse}
          sessions={sessions}
          activeId={activeId}
          streamingSessionIds={streamingSessionIds}
          onSelectSession={onSelectSession}
          onNewChat={onNewChat}
        />
      </div>
      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-white">
        {children}
      </div>
    </div>
  );
}
