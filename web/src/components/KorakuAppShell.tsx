"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useState, type ReactNode } from "react";
import { KorakuChatProvider } from "@/context/KorakuChatContext";
import { useKorakuChat } from "@/hooks/useKorakuChat";
import { APP_BASE, isAppChatRoute } from "@/lib/app-path";
import { AppChrome } from "@/components/AppChrome";
import { ChatConversation } from "@/components/ChatApp";

export function KorakuAppShell({ children }: { children: ReactNode }) {
  const chat = useKorakuChat();
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname() || "";
  const router = useRouter();

  const onSelectSession = useCallback(
    (id: string) => {
      chat.selectSession(id);
      if (!isAppChatRoute(pathname)) {
        router.push(APP_BASE);
      }
    },
    [chat, pathname, router],
  );

  const onNewChat = useCallback(async () => {
    await chat.newChat();
    if (!isAppChatRoute(pathname)) {
      router.push(APP_BASE);
    }
  }, [chat, pathname, router]);

  const onDeleteChat = useCallback(async (id: string) => {
    await chat.deleteSession(id);
  }, [chat]);

  return (
    <KorakuChatProvider value={chat}>
      <AppChrome
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        chatsLoading={!chat.hydrated}
        sessions={chat.sessions}
        activeId={chat.activeId}
        streamingSessionIds={chat.streamingSessionIds}
        onSelectSession={onSelectSession}
        onNewChat={onNewChat}
        onDeleteChat={onDeleteChat}
      >
        {isAppChatRoute(pathname) ? <ChatConversation /> : children}
      </AppChrome>
    </KorakuChatProvider>
  );
}
