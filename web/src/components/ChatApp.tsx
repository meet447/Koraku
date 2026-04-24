"use client";

import { useState } from "react";
import clsx from "clsx";
import { PanelRight } from "lucide-react";
import { useKorakuChatContext } from "@/context/KorakuChatContext";
import { Composer } from "./Composer";
import { MessageQueueBar } from "./MessageQueueBar";
import { ToolTimeline } from "./ToolTimeline";
import { MarkdownBody } from "./MarkdownBody";
import { AgentBusyRow } from "./AgentBusyRow";
import { BrandMark } from "./BrandMark";
import { WorkspacePanel } from "./WorkspacePanel";

function ChatMessagesSkeleton() {
  const block = (key: string) => (
    <div key={key} className="mb-10 space-y-4">
      <div className="flex justify-end">
        <div className="h-11 w-[min(72%,18rem)] animate-pulse rounded-3xl bg-neutral-100" />
      </div>
      <div className="space-y-2.5 pl-1">
        <div className="h-3.5 w-[78%] max-w-xl animate-pulse rounded-md bg-neutral-100" />
        <div className="h-3.5 w-[58%] max-w-md animate-pulse rounded-md bg-neutral-100" />
        <div className="mt-3 h-28 w-full max-w-2xl animate-pulse rounded-2xl bg-neutral-50" />
      </div>
    </div>
  );
  return (
    <div className="space-y-2" aria-busy aria-label="Loading conversation">
      {block("a")}
      {block("b")}
    </div>
  );
}

/** Main chat column; must render inside ``KorakuAppShell`` (provides chat context + chrome). */
export function ChatConversation() {
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const {
    hydrated,
    messagesLoadingSessionIds,
    activeId,
    messages,
    busy,
    streamingSessionIds,
    queuedMessages,
    removeQueuedMessage,
    send,
    serverChatSessionByUi,
  } = useKorakuChatContext();

  const backendChatSessionId = serverChatSessionByUi[activeId] ?? null;

  const chatMainLoading =
    !hydrated ||
    (Boolean(activeId) && messagesLoadingSessionIds.includes(activeId));

  const lastAssistant = [...messages]
    .reverse()
    .find((m) => m.role === "assistant");

  return (
    <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-white">
      <div className="flex min-h-0 flex-1 flex-row overflow-hidden">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="flex shrink-0 items-center justify-end gap-3 border-b border-neutral-100/90 bg-white/90 px-4 py-2">
            <button
              type="button"
              onClick={() => setWorkspaceOpen((o) => !o)}
              aria-pressed={workspaceOpen}
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold shadow-sm transition-colors",
                workspaceOpen
                  ? "border-neutral-300 bg-neutral-100 text-koraku-ink"
                  : "border-neutral-200 bg-white text-koraku-ink hover:bg-neutral-50",
              )}
            >
              <PanelRight
                className={clsx(
                  "h-3.5 w-3.5",
                  workspaceOpen ? "text-koraku-ink" : "text-neutral-500",
                )}
                aria-hidden
              />
              Workspace
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain">
            <div className="mx-auto max-w-3xl px-4 py-8 pb-6">
              {chatMainLoading ? (
                <ChatMessagesSkeleton />
              ) : (
                <>
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
                    {busy && m.id === lastAssistant?.id ? (
                      <AgentBusyRow startedAtMs={m.run.streamStartedAt!} />
                    ) : null}
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
                </>
              )}
            </div>
          </div>

          <div
            className={clsx(
              "shrink-0 bg-white/65 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur-2xl backdrop-saturate-150",
              chatMainLoading && "pointer-events-none opacity-60",
            )}
          >
            <MessageQueueBar items={queuedMessages} onRemove={removeQueuedMessage} />
            <Composer
              busy={busy}
              disabled={chatMainLoading}
              placeholder={busy ? "Give Koraku a follow-up…" : "Ask anything"}
              onSend={send}
            />
          </div>
        </section>

        <WorkspacePanel
          visible={workspaceOpen}
          onClose={() => setWorkspaceOpen(false)}
          serverSessionId={backendChatSessionId}
        />
      </div>
    </main>
  );
}
