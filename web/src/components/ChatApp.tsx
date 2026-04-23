"use client";

import { useState } from "react";
import { useKorakuChat } from "@/hooks/useKorakuChat";
import { AppChrome } from "./AppChrome";
import { Composer } from "./Composer";
import { MessageQueueBar } from "./MessageQueueBar";
import { ToolTimeline } from "./ToolTimeline";
import { MarkdownBody } from "./MarkdownBody";
import { AgentBusyRow } from "./AgentBusyRow";
import { BrandMark } from "./BrandMark";

export function ChatApp() {
  const [collapsed, setCollapsed] = useState(false);
  const {
    sessions,
    activeId,
    messages,
    busy,
    queuedMessages,
    removeQueuedMessage,
    send,
    newChat,
    selectSession,
  } = useKorakuChat();

  const lastAssistant = [...messages]
    .reverse()
    .find((m) => m.role === "assistant");

  return (
    <AppChrome
      collapsed={collapsed}
      onToggleCollapse={() => setCollapsed((c) => !c)}
      sessions={sessions}
      activeId={activeId}
      onSelectSession={selectSession}
      onNewChat={newChat}
    >
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain">
          <div className="mx-auto max-w-3xl px-4 py-8 pb-6">
            {messages.length === 0 && (
              <div className="py-16 text-center">
                <div className="mx-auto mb-4 flex justify-center">
                  <BrandMark
                    size={56}
                    priority
                    className="shadow-md ring-neutral-200/90"
                  />
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-koraku-ink">
                  Koraku
                </h1>
                <p className="mt-2 text-sm font-medium text-koraku-muted">
                  Light, fast agent — ask anything to get started.
                </p>
              </div>
            )}

            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="mb-6 flex justify-end">
                  <div className="max-w-[85%] space-y-2 rounded-3xl bg-neutral-100 px-4 py-3 text-[15px] font-medium text-koraku-ink">
                    {m.images && m.images.length > 0 ? (
                      <div className="flex flex-wrap justify-end gap-2">
                        {m.images.map((im) => (
                          <div
                            key={im.id}
                            className="h-28 w-28 overflow-hidden rounded-2xl border border-neutral-200/80 bg-white"
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={im.previewUrl}
                              alt=""
                              className="h-full w-full object-cover"
                            />
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {m.text ? <p className="whitespace-pre-wrap">{m.text}</p> : null}
                  </div>
                </div>
              ) : (
                <div key={m.id} className="mb-10">
                  <ToolTimeline
                    rows={m.run.timeline}
                    activeThought={m.run.activeThought}
                    toolCallCount={m.run.toolInvocations}
                  />
                  {m.run.assistantMarkdown ? (
                    <MarkdownBody source={m.run.assistantMarkdown} />
                  ) : null}
                  {busy && m.id === lastAssistant?.id ? <AgentBusyRow /> : null}
                  {!m.run.assistantMarkdown &&
                  !busy &&
                  m.id === lastAssistant?.id ? (
                    <p className="mt-2 text-sm text-neutral-400">
                      No assistant text was returned.
                    </p>
                  ) : null}
                  {m.run.error ? (
                    <p className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-800">
                      {m.run.error}
                    </p>
                  ) : null}
                  {!(busy && m.id === lastAssistant?.id) ? (
                    <p className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
                      {m.run.statusText}
                      {m.run.dropdownModelLabel && m.run.statusText !== "Done"
                        ? ` · ${m.run.dropdownModelLabel}`
                        : ""}
                    </p>
                  ) : null}
                </div>
              ),
            )}

          </div>
        </div>

        <div className="shrink-0 bg-white/65 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur-2xl backdrop-saturate-150">
          <MessageQueueBar items={queuedMessages} onRemove={removeQueuedMessage} />
          <Composer
            busy={busy}
            placeholder={
              busy ? "Give Koraku a follow-up…" : "Ask anything"
            }
            onSend={send}
          />
        </div>
      </main>
    </AppChrome>
  );
}
