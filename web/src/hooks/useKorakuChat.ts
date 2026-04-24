"use client";

import { flushSync } from "react-dom";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MutableRefObject,
} from "react";
import {
  applyKorakuSseEvent,
  initialRunState,
  parseKorakuEventInner,
  type RunState,
} from "@/lib/korakuReducer";
import type { ChatExecutionSurface, ComposerImage } from "@/components/Composer";
import type { QueuedMessagePreview } from "@/components/MessageQueueBar";
import { createBrowserSupabaseClient } from "@/lib/supabase/browser";

export type ChatMessage =
  | {
      id: string;
      role: "user";
      text: string;
      images?: { id: string; previewUrl: string }[];
    }
  | { id: string; role: "assistant"; run: RunState };

/** Max agent streams open at once across all sidebar threads. */
export const MAX_CONCURRENT_CHAT_STREAMS = 3;

export type ChatSession = { id: string; title: string };

export type OutboundJob = {
  id: string;
  text: string;
  provider: string;
  model: string;
  dropdownModelLabel: string;
  images: ComposerImage[];
  executionTarget: ChatExecutionSurface;
};

function uid(): string {
  return crypto.randomUUID();
}

function parseSseBlock(raw: string): { event: string; data: string } {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    const L = line.replace(/\r$/, "");
    if (L.startsWith("event:")) event = L.slice(6).trim();
    else if (L.startsWith("data:")) dataLines.push(L.slice(5).trimStart());
  }
  return { event, data: dataLines.join("\n") };
}

function jobPreviewText(job: OutboundJob): string {
  const tag = job.executionTarget === "local" ? " · Local" : " · Cloud";
  const t = job.text.trim();
  if (t) {
    const base = t.length > 120 ? `${t.slice(0, 117)}…` : t;
    return `${base}${tag}`;
  }
  if (job.images.length > 1) return `${job.images.length} images${tag}`;
  if (job.images.length === 1) return `Image${tag}`;
  return `·${tag}`;
}

function rememberServerChatSession(
  uiSessionId: string,
  payload: Record<string, unknown>,
  mapRef: MutableRefObject<Record<string, string>>,
) {
  const t = String(payload.type || "");
  if (t === "koraku.started") {
    const d = payload.data as Record<string, unknown> | undefined;
    const id = d?.chatSessionId;
    if (typeof id === "string" && id.length > 8) mapRef.current[uiSessionId] = id;
    return;
  }
  if (t === "agent.mode") {
    const d = payload.data as Record<string, unknown> | undefined;
    const id = d?.session_id;
    if (typeof id === "string" && id.length > 8) mapRef.current[uiSessionId] = id;
    return;
  }
  if (t === "koraku.event") {
    const inner = parseKorakuEventInner(payload.data);
    if (
      inner &&
      inner.type === "koraku.trace" &&
      inner.trace === "mode" &&
      inner.data &&
      typeof inner.data === "object"
    ) {
      const id = (inner.data as Record<string, unknown>).session_id;
      if (typeof id === "string" && id.length > 8) mapRef.current[uiSessionId] = id;
    }
  }
}

export function useKorakuChat() {
  const [sessions, setSessions] = useState<ChatSession[]>([
    { id: "1", title: "New chat" },
  ]);
  const [activeId, setActiveId] = useState("1");
  const [messagesBySession, setMessagesBySession] = useState<
    Record<string, ChatMessage[]>
  >({ "1": [] });
  /** Session ids with an active POST /stream (for sidebar + composer). */
  const [streamingSessionIds, setStreamingSessionIds] = useState<string[]>([]);
  const [queuedMessages, setQueuedMessages] = useState<QueuedMessagePreview[]>([]);
  const streamingSidsRef = useRef<Set<string>>(new Set());
  const abortBySessionRef = useRef<Record<string, AbortController>>({});
  const serverChatSessionRef = useRef<Record<string, string>>({});
  /** UI session id → server chat UUID (for workspace API after first cloud stream). */
  const [serverChatSessionByUi, setServerChatSessionByUi] = useState<
    Record<string, string>
  >({});
  const activeIdRef = useRef(activeId);
  const sessionsRef = useRef(sessions);
  /** FIFO outbound messages per UI session when that session already has a stream or global cap is hit. */
  const queuesRef = useRef<Record<string, OutboundJob[]>>({});
  const runOutboundJobRef = useRef<(sid: string, job: OutboundJob) => void>(() => {});
  const tryDrainGlobalQueueRef = useRef<() => void>(() => {});

  const messages = messagesBySession[activeId] ?? [];
  const busy = streamingSessionIds.includes(activeId);

  const markStreamStart = useCallback((sid: string) => {
    streamingSidsRef.current.add(sid);
    setStreamingSessionIds(Array.from(streamingSidsRef.current));
  }, []);

  const markStreamEnd = useCallback((sid: string) => {
    streamingSidsRef.current.delete(sid);
    setStreamingSessionIds(Array.from(streamingSidsRef.current));
  }, []);

  useEffect(() => {
    activeIdRef.current = activeId;
    const q = queuesRef.current[activeId] ?? [];
    setQueuedMessages(q.map((j) => ({ id: j.id, text: jobPreviewText(j) })));
  }, [activeId]);

  useEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);

  useEffect(
    () => () => {
      for (const c of Object.values(abortBySessionRef.current)) {
        c.abort();
      }
      abortBySessionRef.current = {};
      streamingSidsRef.current.clear();
    },
    [],
  );

  const updateAssistantRun = useCallback(
    (sessionId: string, assistantMessageId: string, updater: (r: RunState) => RunState) => {
      setMessagesBySession((prev) => {
        const list = [...(prev[sessionId] ?? [])];
        const i = list.findIndex((m) => m.id === assistantMessageId);
        if (i === -1) return prev;
        const row = list[i]!;
        if (row.role !== "assistant") return prev;
        const nextRun = updater(row.run);
        list[i] = { ...row, run: nextRun };
        return { ...prev, [sessionId]: list };
      });
    },
    [],
  );

  const syncQueueUi = useCallback((sid: string) => {
    const q = queuesRef.current[sid] ?? [];
    if (sid === activeIdRef.current) {
      setQueuedMessages(q.map((j) => ({ id: j.id, text: jobPreviewText(j) })));
    }
  }, []);

  const removeQueuedMessage = useCallback(
    (messageId: string) => {
      const sid = activeIdRef.current;
      const arr = queuesRef.current[sid];
      if (!arr) return;
      queuesRef.current[sid] = arr.filter((j) => j.id !== messageId);
      syncQueueUi(sid);
    },
    [syncQueueUi],
  );

  const tryDrainGlobalQueue = useCallback(() => {
    while (streamingSidsRef.current.size < MAX_CONCURRENT_CHAT_STREAMS) {
      let pickedSid: string | null = null;
      for (const s of sessionsRef.current) {
        if (streamingSidsRef.current.has(s.id)) continue;
        const q = queuesRef.current[s.id];
        if (q?.length) {
          pickedSid = s.id;
          break;
        }
      }
      if (!pickedSid) break;
      const arr = queuesRef.current[pickedSid];
      const nextJob = arr?.shift();
      if (!nextJob) break;
      syncQueueUi(pickedSid);
      runOutboundJobRef.current(pickedSid, nextJob);
    }
  }, [syncQueueUi]);

  const runOutboundJob = useCallback(
    (sid: string, job: OutboundJob) => {
      if (streamingSidsRef.current.has(sid)) return;
      if (streamingSidsRef.current.size >= MAX_CONCURRENT_CHAT_STREAMS) return;

      const trimmed = job.text.trim();
      const imgs = job.images.filter((i) => i.data.length > 0);
      const label =
        (job.dropdownModelLabel || "").trim() || (job.model || "").trim() || "";

      const userMsgId = uid();
      const assistantMsgId = uid();
      const userImages =
        imgs.length > 0
          ? imgs.map((i) => ({
              id: i.id,
              previewUrl: `data:${i.media_type};base64,${i.data}`,
            }))
          : undefined;

      markStreamStart(sid);

      flushSync(() => {
        setMessagesBySession((prev) => ({
          ...prev,
          [sid]: [
            ...(prev[sid] ?? []),
            { id: userMsgId, role: "user", text: trimmed, images: userImages },
            {
              id: assistantMsgId,
              role: "assistant",
              run: {
                ...initialRunState(),
                dropdownModelLabel: label,
                streamStartedAt: Date.now(),
              },
            },
          ],
        }));
      });

      const nextTitle = trimmed
        ? trimmed.length > 48
          ? `${trimmed.slice(0, 46)}…`
          : trimmed
        : imgs.length > 1
          ? "Images"
          : "Image";

      setSessions((prev) =>
        prev.map((s) =>
          s.id === sid && (s.title === "New chat" || !s.title)
            ? { ...s, title: nextTitle }
            : s,
        ),
      );

      const controller = new AbortController();
      abortBySessionRef.current[sid] = controller;

      const serverSid = (serverChatSessionRef.current[sid] ?? "").trim();

      let clientTz = "";
      let clientLocale = "";
      try {
        clientTz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
      } catch {
        /* ignore */
      }
      try {
        clientLocale = typeof navigator !== "undefined" ? navigator.language : "";
      } catch {
        /* ignore */
      }

      const body: Record<string, unknown> = {
        msg: trimmed,
        model: job.model || "",
        provider: job.provider || "",
        client_tz: clientTz || null,
        client_locale: clientLocale || null,
        images: imgs.map((i) => ({ media_type: i.media_type, data: i.data })),
      };
      if (serverSid) body.session_id = serverSid;
      body.execution_target = job.executionTarget;

      void (async () => {
        try {
          const streamHeaders: Record<string, string> = {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          };
          try {
            const supabase = createBrowserSupabaseClient();
            const { data } = await supabase.auth.getSession();
            if (data.session?.access_token) {
              streamHeaders.Authorization = `Bearer ${data.session.access_token}`;
            }
          } catch {
            /* Supabase not configured in env — Composio falls back to backend default user */
          }
          const res = await fetch("/koraku-api/stream", {
            method: "POST",
            headers: streamHeaders,
            body: JSON.stringify(body),
            signal: controller.signal,
          });

          if (!res.ok) {
            const errText = await res.text().catch(() => res.statusText);
            updateAssistantRun(sid, assistantMsgId, (r) => ({
              ...r,
              error: r.error || `HTTP ${res.status}: ${errText.slice(0, 400)}`,
              statusText: "Request failed",
            }));
            return;
          }

          const reader = res.body?.getReader();
          if (!reader) {
            updateAssistantRun(sid, assistantMsgId, (r) => ({
              ...r,
              error: r.error || "No response body",
              statusText: "Stream error",
            }));
            return;
          }

          const decoder = new TextDecoder();
          let buffer = "";

          const pump = async (): Promise<void> => {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              buffer += decoder.decode(value, { stream: true });
              const payloads: Record<string, unknown>[] = [];
              let sawStreamDone = false;
              for (;;) {
                const sepRn = buffer.indexOf("\r\n\r\n");
                const sepN = buffer.indexOf("\n\n");
                let sep = -1;
                let skip = 0;
                if (sepRn !== -1 && (sepN === -1 || sepRn <= sepN)) {
                  sep = sepRn;
                  skip = 4;
                } else if (sepN !== -1) {
                  sep = sepN;
                  skip = 2;
                }
                if (sep === -1) break;
                const rawBlock = buffer.slice(0, sep);
                buffer = buffer.slice(sep + skip);
                const { event, data } = parseSseBlock(rawBlock);
                if (event === "done") {
                  sawStreamDone = true;
                  break;
                }
                if (event === "ping") continue;
                if (!data) continue;
                try {
                  payloads.push(JSON.parse(data) as Record<string, unknown>);
                } catch {
                  continue;
                }
              }
              for (const payload of payloads) {
                rememberServerChatSession(sid, payload, serverChatSessionRef);
                const mapped = serverChatSessionRef.current[sid]?.trim();
                if (mapped) {
                  setServerChatSessionByUi((prev) =>
                    prev[sid] === mapped ? prev : { ...prev, [sid]: mapped },
                  );
                }
                flushSync(() => {
                  updateAssistantRun(sid, assistantMsgId, (r) =>
                    applyKorakuSseEvent(r, payload),
                  );
                });
              }
              if (payloads.length > 1) {
                await new Promise<void>((resolve) => setTimeout(resolve, 0));
              }
              if (sawStreamDone) return;
            }
          };

          await pump();
        } catch (e) {
          if ((e as Error)?.name === "AbortError") return;
          updateAssistantRun(sid, assistantMsgId, (r) => ({
            ...r,
            error: r.error || String((e as Error)?.message || e),
            statusText: "Connection error",
          }));
        } finally {
          if (abortBySessionRef.current[sid] === controller) {
            delete abortBySessionRef.current[sid];
          }
          if (controller.signal.aborted) {
            markStreamEnd(sid);
            queueMicrotask(() => tryDrainGlobalQueueRef.current());
            return;
          }
          markStreamEnd(sid);
          const arrSame = queuesRef.current[sid];
          const nextSame = arrSame?.length ? arrSame.shift()! : undefined;
          syncQueueUi(sid);
          if (nextSame) {
            runOutboundJobRef.current(sid, nextSame);
          } else {
            queueMicrotask(() => tryDrainGlobalQueueRef.current());
          }
        }
      })();
    },
    [markStreamEnd, markStreamStart, syncQueueUi, updateAssistantRun],
  );

  runOutboundJobRef.current = runOutboundJob;
  tryDrainGlobalQueueRef.current = tryDrainGlobalQueue;

  const send = useCallback(
    (
      text: string,
      provider: string,
      model: string,
      dropdownModelLabel: string,
      images: ComposerImage[] = [],
      executionTarget: ChatExecutionSurface = "cloud",
    ) => {
      const trimmed = text.trim();
      const imgs = images.filter((i) => i.data.length > 0);
      if (!trimmed && imgs.length === 0) return;

      const sid = activeIdRef.current;
      const job: OutboundJob = {
        id: uid(),
        text: trimmed,
        provider,
        model,
        dropdownModelLabel,
        images: imgs.map((i) => ({ ...i })),
        executionTarget,
      };

      if (streamingSidsRef.current.has(sid)) {
        queuesRef.current[sid] ??= [];
        queuesRef.current[sid].push(job);
        syncQueueUi(sid);
        return;
      }

      if (streamingSidsRef.current.size >= MAX_CONCURRENT_CHAT_STREAMS) {
        queuesRef.current[sid] ??= [];
        queuesRef.current[sid].push(job);
        syncQueueUi(sid);
        return;
      }

      runOutboundJob(sid, job);
    },
    [runOutboundJob, syncQueueUi],
  );

  const newChat = useCallback(() => {
    const id = uid();
    setSessions((s) => [{ id, title: "New chat" }, ...s]);
    setMessagesBySession((m) => ({ ...m, [id]: [] }));
    setActiveId(id);
    setQueuedMessages([]);
  }, []);

  const selectSession = useCallback(
    (id: string) => {
      setActiveId(id);
      const q = queuesRef.current[id] ?? [];
      setQueuedMessages(q.map((j) => ({ id: j.id, text: jobPreviewText(j) })));
    },
    [],
  );

  return {
    sessions,
    activeId,
    messages,
    busy,
    streamingSessionIds,
    queuedMessages,
    removeQueuedMessage,
    send,
    newChat,
    selectSession,
    serverChatSessionByUi,
  };
}
