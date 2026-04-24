"use client";

import { flushSync } from "react-dom";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
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

function deserializeRunState(raw: unknown): RunState {
  const b = initialRunState();
  if (!raw || typeof raw !== "object") return b;
  const o = raw as Partial<RunState>;
  return {
    ...b,
    ...o,
    timeline: Array.isArray(o.timeline) ? o.timeline : b.timeline,
    pendingToolByUseId:
      o.pendingToolByUseId && typeof o.pendingToolByUseId === "object"
        ? o.pendingToolByUseId
        : b.pendingToolByUseId,
    blockKindByIndex:
      o.blockKindByIndex && typeof o.blockKindByIndex === "object"
        ? o.blockKindByIndex
        : b.blockKindByIndex,
    blockNameByIndex:
      o.blockNameByIndex && typeof o.blockNameByIndex === "object"
        ? o.blockNameByIndex
        : b.blockNameByIndex,
    partialJsonByIndex:
      o.partialJsonByIndex && typeof o.partialJsonByIndex === "object"
        ? o.partialJsonByIndex
        : b.partialJsonByIndex,
  };
}

function apiRowToChatMessage(row: {
  id: string;
  role: string;
  contentJson: unknown;
}): ChatMessage | null {
  const c = row.contentJson;
  if (row.role === "user") {
    if (!c || typeof c !== "object") {
      return { id: row.id, role: "user", text: "" };
    }
    const o = c as Record<string, unknown>;
    const text = typeof o.text === "string" ? o.text : "";
    let images: { id: string; previewUrl: string }[] | undefined;
    if (Array.isArray(o.images)) {
      images = o.images
        .map((x) => {
          if (!x || typeof x !== "object") return null;
          const im = x as Record<string, unknown>;
          const id = typeof im.id === "string" ? im.id : uid();
          const previewUrl = typeof im.previewUrl === "string" ? im.previewUrl : "";
          return previewUrl ? { id, previewUrl } : null;
        })
        .filter((x): x is { id: string; previewUrl: string } => x != null);
    }
    return { id: row.id, role: "user", text, images: images?.length ? images : undefined };
  }
  if (row.role === "assistant") {
    const runRaw =
      c && typeof c === "object" && "run" in (c as object)
        ? (c as { run: unknown }).run
        : c;
    return { id: row.id, role: "assistant", run: deserializeRunState(runRaw) };
  }
  return null;
}

function chatMessageToApiRow(m: ChatMessage): {
  id: string;
  role: string;
  contentJson: unknown;
} {
  if (m.role === "user") {
    const images = m.images?.map(({ id, previewUrl }) => ({
      id,
      previewUrl: previewUrl.length < 48_000 ? previewUrl : "",
    }));
    return {
      id: m.id,
      role: "user",
      contentJson: {
        text: m.text,
        ...(images?.some((i) => i.previewUrl) ? { images } : {}),
      },
    };
  }
  return { id: m.id, role: "assistant", contentJson: { run: m.run } };
}

export function useKorakuChat() {
  const [hydrated, setHydrated] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState("");
  const [messagesBySession, setMessagesBySession] = useState<
    Record<string, ChatMessage[]>
  >({});
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
  const messagesBySessionRef = useRef<Record<string, ChatMessage[]>>({});
  const persistenceEnabledRef = useRef(false);
  const messagesLoadedForThreadRef = useRef<Set<string>>(new Set());
  const activeIdRef = useRef(activeId);
  const sessionsRef = useRef(sessions);
  /** FIFO outbound messages per UI session when that session already has a stream or global cap is hit. */
  const queuesRef = useRef<Record<string, OutboundJob[]>>({});
  const runOutboundJobRef = useRef<(sid: string, job: OutboundJob) => void>(() => {});
  const tryDrainGlobalQueueRef = useRef<() => void>(() => {});
  const newChatInFlightRef = useRef(false);

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

  useLayoutEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);

  useLayoutEffect(() => {
    messagesBySessionRef.current = messagesBySession;
  }, [messagesBySession]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const supabase = createBrowserSupabaseClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (cancelled) return;
        if (!session) {
          const id = uid();
          persistenceEnabledRef.current = false;
          setSessions([{ id, title: "New chat" }]);
          setActiveId(id);
          setMessagesBySession({ [id]: [] });
          messagesLoadedForThreadRef.current = new Set([id]);
          setHydrated(true);
          return;
        }
        const tr = await fetch("/api/chat/threads", { credentials: "include" });
        if (cancelled) return;
        if (!tr.ok) {
          const id = uid();
          persistenceEnabledRef.current = false;
          setSessions([{ id, title: "New chat" }]);
          setActiveId(id);
          setMessagesBySession({ [id]: [] });
          messagesLoadedForThreadRef.current = new Set([id]);
          setHydrated(true);
          return;
        }
        const payload = (await tr.json()) as { threads?: { id: string; title: string }[] };
        let list = payload.threads ?? [];
        if (list.length === 0) {
          const cr = await fetch("/api/chat/threads", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: "{}",
          });
          if (cancelled) return;
          if (!cr.ok) {
            const id = uid();
            persistenceEnabledRef.current = false;
            setSessions([{ id, title: "New chat" }]);
            setActiveId(id);
            setMessagesBySession({ [id]: [] });
            messagesLoadedForThreadRef.current = new Set([id]);
            setHydrated(true);
            return;
          }
          const row = (await cr.json()) as { id: string; title: string };
          list = [{ id: row.id, title: row.title }];
        }
        if (cancelled) return;
        persistenceEnabledRef.current = true;
        const sessList = list.map((t) => ({ id: t.id, title: t.title || "New chat" }));
        const firstId = sessList[0]!.id;
        for (const s of sessList) {
          serverChatSessionRef.current[s.id] = s.id;
        }
        setServerChatSessionByUi(Object.fromEntries(sessList.map((s) => [s.id, s.id])));
        const msgMap: Record<string, ChatMessage[]> = Object.fromEntries(
          sessList.map((s) => [s.id, [] as ChatMessage[]]),
        );
        const mr = await fetch(`/api/chat/threads/${firstId}/messages`, {
          credentials: "include",
        });
        if (cancelled) return;
        if (mr.ok) {
          const mp = (await mr.json()) as {
            messages?: { id: string; role: string; contentJson: unknown }[];
          };
          msgMap[firstId] = (mp.messages ?? [])
            .map(apiRowToChatMessage)
            .filter((m): m is ChatMessage => m != null);
        }
        messagesLoadedForThreadRef.current = new Set([firstId]);
        setSessions(sessList);
        setActiveId(firstId);
        setMessagesBySession(msgMap);
        setHydrated(true);
      } catch {
        if (cancelled) return;
        const id = uid();
        persistenceEnabledRef.current = false;
        setSessions([{ id, title: "New chat" }]);
        setActiveId(id);
        setMessagesBySession({ [id]: [] });
        messagesLoadedForThreadRef.current = new Set([id]);
        setHydrated(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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

  const persistThreadToServer = useCallback(async (threadId: string) => {
    if (!persistenceEnabledRef.current) return;
    const msgs = messagesBySessionRef.current[threadId] ?? [];
    if (msgs.length === 0) return;
    const title =
      sessionsRef.current.find((s) => s.id === threadId)?.title?.trim() || "New chat";
    try {
      await fetch(`/api/chat/threads/${threadId}/messages`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: msgs.map(chatMessageToApiRow),
          title,
        }),
      });
    } catch {
      /* ignore */
    }
  }, []);

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
          markStreamEnd(sid);
          const aborted = controller.signal.aborted;
          queueMicrotask(() => {
            void persistThreadToServer(sid);
            if (aborted) tryDrainGlobalQueueRef.current();
          });
          if (aborted) return;
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
    [markStreamEnd, markStreamStart, persistThreadToServer, syncQueueUi, updateAssistantRun],
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
      if (!hydrated) return;

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
    [hydrated, runOutboundJob, syncQueueUi],
  );

  const newChat = useCallback(async () => {
    const sid = activeIdRef.current;
    if (sid) {
      const msgs = messagesBySessionRef.current[sid] ?? [];
      const sessionRow = sessionsRef.current.find((x) => x.id === sid);
      const title = sessionRow?.title?.trim() ?? "";
      const defaultTitle = !title || title === "New chat";
      if (
        msgs.length === 0 &&
        defaultTitle &&
        !streamingSidsRef.current.has(sid)
      ) {
        return;
      }
    }

    if (newChatInFlightRef.current) return;
    newChatInFlightRef.current = true;
    try {
      if (persistenceEnabledRef.current) {
        try {
          const res = await fetch("/api/chat/threads", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: "{}",
          });
          if (res.ok) {
            const row = (await res.json()) as { id: string; title: string };
            const id = row.id;
            serverChatSessionRef.current[id] = id;
            setServerChatSessionByUi((prev) => ({ ...prev, [id]: id }));
            setSessions((s) => [{ id, title: row.title || "New chat" }, ...s]);
            setMessagesBySession((m) => ({ ...m, [id]: [] }));
            setActiveId(id);
            setQueuedMessages([]);
            messagesLoadedForThreadRef.current.add(id);
            return;
          }
        } catch {
          /* fall through to local-only chat */
        }
      }
      const id = uid();
      setSessions((s) => [{ id, title: "New chat" }, ...s]);
      setMessagesBySession((m) => ({ ...m, [id]: [] }));
      setActiveId(id);
      setQueuedMessages([]);
      messagesLoadedForThreadRef.current.add(id);
    } finally {
      newChatInFlightRef.current = false;
    }
  }, []);

  const selectSession = useCallback((id: string) => {
    setActiveId(id);
    const q = queuesRef.current[id] ?? [];
    setQueuedMessages(q.map((j) => ({ id: j.id, text: jobPreviewText(j) })));

    if (!persistenceEnabledRef.current) return;
    if (messagesLoadedForThreadRef.current.has(id)) return;
    messagesLoadedForThreadRef.current.add(id);

    void (async () => {
      try {
        const res = await fetch(`/api/chat/threads/${id}/messages`, {
          credentials: "include",
        });
        if (!res.ok) {
          messagesLoadedForThreadRef.current.delete(id);
          return;
        }
        const body = (await res.json()) as {
          messages?: { id: string; role: string; contentJson: unknown }[];
        };
        const list = (body.messages ?? [])
          .map(apiRowToChatMessage)
          .filter((m): m is ChatMessage => m != null);
        setMessagesBySession((prev) => ({ ...prev, [id]: list }));
      } catch {
        messagesLoadedForThreadRef.current.delete(id);
      }
    })();
  }, []);

  const deleteSession = useCallback(
    async (id: string) => {
      if (!sessionsRef.current.some((s) => s.id === id)) return;

      const controller = abortBySessionRef.current[id];
      if (controller) {
        controller.abort();
        delete abortBySessionRef.current[id];
      }
      markStreamEnd(id);
      delete queuesRef.current[id];
      delete serverChatSessionRef.current[id];
      messagesLoadedForThreadRef.current.delete(id);

      if (persistenceEnabledRef.current) {
        try {
          await fetch(`/api/chat/threads/${id}`, {
            method: "DELETE",
            credentials: "include",
          });
        } catch {
          /* still remove locally */
        }
      }

      const wasActive = activeIdRef.current === id;
      const nextSessions = sessionsRef.current.filter((s) => s.id !== id);

      if (nextSessions.length === 0) {
        if (persistenceEnabledRef.current) {
          try {
            const res = await fetch("/api/chat/threads", {
              method: "POST",
              credentials: "include",
              headers: { "Content-Type": "application/json" },
              body: "{}",
            });
            if (res.ok) {
              const row = (await res.json()) as { id: string; title: string };
              const nid = row.id;
              serverChatSessionRef.current = { [nid]: nid };
              setServerChatSessionByUi({ [nid]: nid });
              setSessions([{ id: nid, title: row.title || "New chat" }]);
              setMessagesBySession({ [nid]: [] });
              setActiveId(nid);
              setQueuedMessages([]);
              messagesLoadedForThreadRef.current = new Set([nid]);
              queueMicrotask(() => tryDrainGlobalQueueRef.current());
              return;
            }
          } catch {
            /* fall through to local-only replacement */
          }
        }
        const nid = uid();
        serverChatSessionRef.current = {};
        setServerChatSessionByUi({});
        setSessions([{ id: nid, title: "New chat" }]);
        setMessagesBySession({ [nid]: [] });
        setActiveId(nid);
        setQueuedMessages([]);
        messagesLoadedForThreadRef.current = new Set([nid]);
        queueMicrotask(() => tryDrainGlobalQueueRef.current());
        return;
      }

      setSessions(nextSessions);
      setMessagesBySession((m) => {
        const n = { ...m };
        delete n[id];
        return n;
      });
      setServerChatSessionByUi((prev) => {
        if (!prev[id]) return prev;
        const n = { ...prev };
        delete n[id];
        return n;
      });

      if (wasActive) {
        const fallbackId = nextSessions[0]!.id;
        setActiveId(fallbackId);
        const q = queuesRef.current[fallbackId] ?? [];
        setQueuedMessages(q.map((j) => ({ id: j.id, text: jobPreviewText(j) })));
      }
      queueMicrotask(() => tryDrainGlobalQueueRef.current());
    },
    [markStreamEnd],
  );

  return {
    hydrated,
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
    deleteSession,
    serverChatSessionByUi,
  };
}

export type KorakuChatApi = ReturnType<typeof useKorakuChat>;
