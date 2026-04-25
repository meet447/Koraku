"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { PanelRight } from "lucide-react";
import { useKorakuChatThread } from "@/context/KorakuChatContext";
import type { ChatMessage } from "@/hooks/useKorakuChat";
import { Composer } from "./Composer";
import { MessageQueueBar } from "./MessageQueueBar";
import { ToolTimeline } from "./ToolTimeline";
import { MarkdownBody } from "./MarkdownBody";
import { AgentBusyRow } from "./AgentBusyRow";
import { BrandMark } from "./BrandMark";
import { WorkspacePanel } from "./WorkspacePanel";
import { TaskRoomPanel } from "./TaskRoomPanel";

/** Use windowed rendering when a thread has at least this many rows. */
const VIRTUALIZE_MESSAGE_COUNT = 10;

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

function ChatMessageRow({
  m,
  busy,
  lastAssistant,
}: {
  m: ChatMessage;
  busy: boolean;
  lastAssistant: Extract<ChatMessage, { role: "assistant" }> | undefined;
}) {
  const isLastAssistant = m.role === "assistant" && lastAssistant?.id === m.id;

  return m.role === "user" ? (
    <div className="mb-6 flex justify-end">
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
    <div className="mb-10">
      <ToolTimeline
        rows={m.run.timeline}
        activeThought={m.run.activeThought}
        toolCallCount={m.run.toolInvocations}
      />
      <TaskRoomPanel plan={m.run.studioPlan} />
      {m.run.assistantMarkdown ? (
        <MarkdownBody
          source={m.run.assistantMarkdown}
          deferHeavyParse={busy && isLastAssistant}
        />
      ) : null}
      {busy && isLastAssistant ? (
        <AgentBusyRow startedAtMs={m.run.streamStartedAt!} />
      ) : null}
      {!m.run.assistantMarkdown && !busy && isLastAssistant ? (
        <p className="mt-2 text-sm text-neutral-400">No assistant text was returned.</p>
      ) : null}
      {m.run.error ? (
        <p className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-800">
          {m.run.error}
        </p>
      ) : null}
      {!(busy && isLastAssistant) ? (
        <p className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
          {m.run.statusText}
          {m.run.dropdownModelLabel && m.run.statusText !== "Done"
            ? ` · ${m.run.dropdownModelLabel}`
            : ""}
        </p>
      ) : null}
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
    queuedMessages,
    removeQueuedMessage,
    send,
    serverChatSessionByUi,
  } = useKorakuChatThread();

  const backendChatSessionId = serverChatSessionByUi[activeId] ?? null;

  const chatMainLoading =
    !hydrated ||
    (Boolean(activeId) && messagesLoadingSessionIds.includes(activeId));

  const lastAssistant = useMemo((): Extract<ChatMessage, { role: "assistant" }> | undefined => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i]!;
      if (m.role === "assistant") return m;
    }
    return undefined;
  }, [messages]);

  const scrollParentRef = useRef<HTMLDivElement>(null);
  const virtualEnabled =
    !chatMainLoading && messages.length >= VIRTUALIZE_MESSAGE_COUNT;

  const rowVirtualizer = useVirtualizer({
    count: virtualEnabled ? messages.length : 0,
    getScrollElement: () => scrollParentRef.current,
    estimateSize: (index) => (messages[index]?.role === "user" ? 100 : 260),
    overscan: 6,
    getItemKey: (index) => messages[index]?.id ?? index,
  });

  useLayoutEffect(() => {
    if (!busy || chatMainLoading || messages.length === 0) return;
    const el = scrollParentRef.current;
    if (!el) return;
    const threshold = 180;
    const { scrollTop, scrollHeight, clientHeight } = el;
    if (scrollHeight - scrollTop - clientHeight < threshold) {
      el.scrollTop = scrollHeight;
    }
  }, [messages, busy, chatMainLoading]);

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

          <div
            ref={scrollParentRef}
            className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain"
          >
            <div className="mx-auto max-w-3xl px-4 py-8 pb-6">
              {chatMainLoading ? (
                <ChatMessagesSkeleton />
              ) : (
                <>
                  {messages.length === 0 && (
                    <div className="py-16 text-center">
                      <div className="mx-auto mb-5 flex justify-center">
                        <BrandMark size={88} priority />
                      </div>
                      <h1 className="text-2xl font-bold tracking-tight text-koraku-ink">
                        Koraku
                      </h1>
                      <p className="mt-2 text-sm font-medium text-koraku-muted">
                        Light, fast agent — ask anything to get started.
                      </p>
                    </div>
                  )}

                  {virtualEnabled ? (
                    <div
                      className="relative w-full"
                      style={{ height: rowVirtualizer.getTotalSize() }}
                    >
                      {rowVirtualizer.getVirtualItems().map((vi) => {
                        const m = messages[vi.index]!;
                        return (
                          <div
                            key={vi.key}
                            data-index={vi.index}
                            ref={rowVirtualizer.measureElement}
                            className="left-0 top-0 w-full pb-0"
                            style={{
                              position: "absolute",
                              transform: `translateY(${vi.start}px)`,
                            }}
                          >
                            <ChatMessageRow
                              m={m}
                              busy={busy}
                              lastAssistant={lastAssistant}
                            />
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    messages.map((m) => (
                      <ChatMessageRow
                        key={m.id}
                        m={m}
                        busy={busy}
                        lastAssistant={lastAssistant}
                      />
                    ))
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
