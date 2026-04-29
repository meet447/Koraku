import {
  formatUrlForTimeline,
  humanizeToolErrorSnippet,
  humanizeToolExecution,
  pageToolLine,
} from "@/lib/toolEventLabels";

export type TimelineRow =
  | { id: string; kind: "thought"; seconds: number; body: string }
  | {
      id: string;
      kind: "tool";
      tool: string;
      label: string;
      detail?: string;
      ok?: boolean;
      /** Present while this row tracks an in-flight page fetch */
      callId?: string;
    };

export type RunState = {
  /** Client epoch ms when this assistant turn began (stable across sidebar remounts). */
  streamStartedAt: number | null;
  /** Per-turn server run id from ``koraku.started`` (optional; for logs / support). */
  runId: string;
  statusText: string;
  error: string | null;
  assistantMarkdown: string;
  /** Same text as the model dropdown option (not raw provider / API id). */
  dropdownModelLabel: string;
  metaModel: string;
  metaProvider: string;
  mode: string;
  maxSteps: number;
  toolsBadges: string[];
  timeline: TimelineRow[];
  activeThought: { started: number; text: string } | null;
  blockKindByIndex: Record<number, string>;
  blockNameByIndex: Record<number, string>;
  partialJsonByIndex: Record<number, string>;
  toolInvocations: number;
  /** Tool calls keyed by tool_use_id until a normalized completion event arrives. */
  pendingToolByUseId: Record<
    string,
    { tool: string; input: unknown; timelineRowId: string }
  >;
};

function rid(): string {
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function initialRunState(): RunState {
  return {
    streamStartedAt: null,
    runId: "",
    statusText: "",
    error: null,
    assistantMarkdown: "",
    dropdownModelLabel: "",
    metaModel: "",
    metaProvider: "",
    mode: "",
    maxSteps: 0,
    toolsBadges: [],
    timeline: [],
    activeThought: null,
    blockKindByIndex: {},
    blockNameByIndex: {},
    partialJsonByIndex: {},
    toolInvocations: 0,
    pendingToolByUseId: {},
  };
}

function finalizeThought(s: RunState): RunState {
  if (!s.activeThought) return s;
  const elapsed = Math.max(0, (Date.now() - s.activeThought.started) / 1000);
  const raw = s.activeThought.text.trim();
  if (!raw) {
    return { ...s, activeThought: null };
  }
  const body =
    raw.length > 14_000 ? `${raw.slice(0, 14_000)}…` : raw || "…";
  const row: TimelineRow = {
    id: rid(),
    kind: "thought",
    seconds: Math.round(elapsed * 10) / 10,
    body,
  };
  return {
    ...s,
    timeline: [...s.timeline, row],
    activeThought: null,
  };
}

function firstUrlInString(s: string): string | undefined {
  const m = s.match(/https?:\/\/[^\s)\]'">]+/);
  return m?.[0];
}

function urlFromToolInput(input: unknown): string | undefined {
  if (!input || typeof input !== "object") return undefined;
  const o = input as Record<string, unknown>;
  const u = o.url;
  return typeof u === "string" ? u.trim() : undefined;
}

function isPageTool(tool: string): boolean {
  return (
    tool === "WebPage" ||
    tool === "WebFetch" ||
    tool === "Firecrawl" ||
    tool === "FirecrawlMap"
  );
}

function toolResultText(block: Record<string, unknown>): string {
  const c = block.content;
  if (typeof c === "string") return c;
  if (Array.isArray(c)) {
    return c
      .map((part) => {
        if (typeof part === "string") return part;
        if (
          part &&
          typeof part === "object" &&
          (part as { type?: string }).type === "text" &&
          typeof (part as { text?: string }).text === "string"
        ) {
          return (part as { text: string }).text;
        }
        return "";
      })
      .join("");
  }
  return String(c ?? "");
}

function handleUserMessage(s: RunState, message: Record<string, unknown>): RunState {
  const content = message.content;
  const blocks = Array.isArray(content)
    ? (content as Record<string, unknown>[])
    : content && typeof content === "object"
      ? [content as Record<string, unknown>]
      : [];
  let next = { ...s };
  for (const block of blocks) {
    if (String(block.type || "") !== "tool_result") continue;
    const id = String(block.tool_use_id || "");
    const pending = id ? next.pendingToolByUseId[id] : undefined;
    const isErr = Boolean(block.is_error);
    const text = toolResultText(block);
    const tool = pending?.tool ?? "tool";
    const input = pending?.input;
    const urlHint = urlFromToolInput(input) ?? firstUrlInString(text);

    if (isPageTool(tool) && pending) {
      const { [id]: _drop, ...restPending } = next.pendingToolByUseId;
      next = { ...next, pendingToolByUseId: restPending };
      const rowId = pending.timelineRowId;
      const line = pageToolLine(
        tool,
        pending.input,
        isErr ? "error" : "done",
      );
      const detail =
        line.detail ?? (urlHint ? formatUrlForTimeline(urlHint) : undefined);
      const timeline = next.timeline.map((r) => {
        if (r.kind !== "tool" || r.id !== rowId) return r;
        return {
          ...r,
          label: line.label,
          detail: detail ?? r.detail,
          ok: !isErr,
          callId: undefined,
        };
      });
      next = { ...next, timeline };
      continue;
    }

    if (isPageTool(tool) && !pending && id) {
      const line = pageToolLine(tool, { url: urlHint } as Record<string, unknown>, isErr ? "error" : "done");
      const row: TimelineRow = {
        id: rid(),
        kind: "tool",
        tool,
        label: line.label,
        detail: line.detail ?? (urlHint ? formatUrlForTimeline(urlHint) : undefined),
        ok: !isErr,
      };
      next = { ...next, timeline: [...next.timeline, row] };
      continue;
    }

    if (isErr) {
      const row: TimelineRow = {
        id: rid(),
        kind: "tool",
        tool,
        label: `Failed: ${tool}`,
        detail: humanizeToolErrorSnippet(text) || urlHint,
        ok: false,
      };
      next = { ...next, timeline: [...next.timeline, row] };
    }
  }
  return next;
}

function handleToolEvent(s: RunState, event: Record<string, unknown>): RunState {
  const phase = String(event.phase || "");
  const id = String(event.tool_use_id || "");
  const tool = String(event.tool_name || "tool");
  const input = event.tool_input;
  const isErr = Boolean(event.is_error || phase === "failed");
  const outputSummary = typeof event.output_summary === "string" ? event.output_summary : "";

  if (phase === "started") {
    const rowId = rid();
    const line = isPageTool(tool)
      ? pageToolLine(tool, input, "pending")
      : humanizeToolExecution(tool, input);
    const row: TimelineRow = {
      id: rowId,
      kind: "tool",
      tool,
      label: line.label,
      detail: line.detail,
      ok: true,
      callId: id || undefined,
    };
    return {
      ...s,
      timeline: [...s.timeline, row],
      pendingToolByUseId: id
        ? {
            ...s.pendingToolByUseId,
            [id]: { tool, input, timelineRowId: rowId },
          }
        : s.pendingToolByUseId,
      toolInvocations: s.toolInvocations + 1,
      statusText: `${line.label}…`,
    };
  }

  if (phase !== "completed" && phase !== "failed") {
    return s;
  }

  const pending = id ? s.pendingToolByUseId[id] : undefined;
  const eventTool = pending?.tool ?? tool;
  const eventInput = pending?.input ?? input;
  const { [id]: _drop, ...restPending } = s.pendingToolByUseId;
  const urlHint = urlFromToolInput(eventInput) ?? firstUrlInString(outputSummary);
  const page = isPageTool(eventTool);
  const line = page
    ? pageToolLine(eventTool, eventInput, isErr ? "error" : "done")
    : humanizeToolExecution(eventTool, eventInput);
  const label = isErr
    ? `Failed: ${eventTool}`
    : page
      ? line.label
      : line.label;
  const detail =
    (isErr ? humanizeToolErrorSnippet(outputSummary) : undefined) ||
    line.detail ||
    (urlHint ? formatUrlForTimeline(urlHint) : undefined);

  if (pending) {
    return {
      ...s,
      pendingToolByUseId: restPending,
      timeline: s.timeline.map((r) => {
        if (r.kind !== "tool" || r.id !== pending.timelineRowId) return r;
        return {
          ...r,
          label,
          detail: detail ?? r.detail,
          ok: !isErr,
          callId: undefined,
        };
      }),
      statusText: isErr ? `Failed: ${eventTool}` : `${line.label}`,
    };
  }

  const row: TimelineRow = {
    id: rid(),
    kind: "tool",
    tool: eventTool,
    label,
    detail,
    ok: !isErr,
  };
  return {
    ...s,
    timeline: [...s.timeline, row],
    pendingToolByUseId: restPending,
    statusText: isErr ? `Failed: ${eventTool}` : `${line.label}`,
  };
}

function handleStreamEvent(s: RunState, ev: Record<string, unknown>): RunState {
  const t = ev.type as string | undefined;
  if (!t) return s;

  if (t === "content_block_start") {
    const block = ev.content_block as Record<string, unknown> | undefined;
    const idx = ev.index as number;
    if (!block || typeof idx !== "number") return s;
    const bType = String(block.type || "");
    let next = { ...s, blockKindByIndex: { ...s.blockKindByIndex, [idx]: bType } };
    if (bType === "thinking") {
      next = finalizeThought(next);
      next = {
        ...next,
        activeThought: { started: Date.now(), text: "" },
      };
    }
    return next;
  }

  if (t === "content_block_delta") {
    const delta = ev.delta as Record<string, unknown> | undefined;
    const idx = ev.index as number;
    if (!delta || typeof idx !== "number") return s;
    const dt = String(delta.type || "");
    if (dt === "thinking_delta" && typeof delta.thinking === "string") {
      if (!s.activeThought) {
        return {
          ...s,
          activeThought: { started: Date.now(), text: delta.thinking },
        };
      }
      return {
        ...s,
        activeThought: {
          ...s.activeThought,
          text: s.activeThought.text + delta.thinking,
        },
      };
    }
    if (dt === "text_delta" && typeof delta.text === "string") {
      const next = finalizeThought(s);
      return {
        ...next,
        assistantMarkdown: next.assistantMarkdown + delta.text,
      };
    }
    return s;
  }

  if (t === "content_block_stop") {
    const idx = ev.index as number;
    if (typeof idx !== "number") return s;
    const kind = s.blockKindByIndex[idx];
    let next = { ...s };
    if (kind === "thinking") {
      next = finalizeThought(next);
    }
    const { [idx]: _i, ...restPart } = next.partialJsonByIndex;
    const { [idx]: _k, ...restKind } = next.blockKindByIndex;
    const { [idx]: _n, ...restName } = next.blockNameByIndex;
    next = {
      ...next,
      partialJsonByIndex: restPart,
      blockKindByIndex: restKind,
      blockNameByIndex: restName,
    };
    return next;
  }

  if (t === "assistant_message") {
    const message = ev.message as Record<string, unknown> | undefined;
    if (!message) return s;
    const content = message.content;
    const blocks = Array.isArray(content)
      ? (content as Record<string, unknown>[])
      : [];
    let text = "";
    for (const b of blocks) {
      if (!b || typeof b !== "object") continue;
      const bt = String((b as { type?: string }).type || "");
      if (bt === "text" && typeof (b as { text?: string }).text === "string") {
        text += (b as { text: string }).text;
      }
    }
    if (!text) return s;
    const next = finalizeThought(s);
    return { ...next, assistantMarkdown: text };
  }

  return s;
}

/** Parse ``koraku.event`` ``data`` (JSON string or object) for reducers and clients. */
export function parseKorakuEventInner(raw: unknown): Record<string, unknown> | null {
  if (!raw) return null;
  if (typeof raw === "object") return raw as Record<string, unknown>;
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return null;
    }
  }
  return null;
}

export function applyKorakuSseEvent(
  s: RunState,
  outer: Record<string, unknown>,
): RunState {
  const typ = String(outer.type || "");
  let next = { ...s };

  if (typ === "koraku.started") {
    const d = outer.data as Record<string, unknown> | undefined;
    const rid = d?.runId != null ? String(d.runId) : "";
    if (d && typeof d.model === "string") {
      next = {
        ...next,
        metaModel: d.model,
        statusText: "Connecting…",
        ...(rid ? { runId: rid } : {}),
      };
    } else if (rid) {
      next = { ...next, runId: rid };
    }
    return next;
  }

  if (typ === "koraku.route_decision") {
    const d = outer.data as Record<string, unknown> | undefined;
    if (d?.model) next = { ...next, metaModel: String(d.model) };
    const meta = d?.meta as Record<string, unknown> | undefined;
    if (meta?.provider) next = { ...next, metaProvider: String(meta.provider) };
    return next;
  }

  if (typ === "koraku.completed") {
    const d = outer.data as Record<string, unknown> | undefined;
    const failed = Boolean(d?.failed);
    const cancelled = Boolean(d?.cancelled);
    const err = d?.error != null ? String(d.error) : "";
    if (failed) {
      next = {
        ...next,
        error: err || "Run failed",
        statusText: "Failed",
      };
    } else if (cancelled) {
      next = { ...next, statusText: "Stopped", error: null };
    } else {
      next = { ...next, statusText: "Done", error: null };
    }
    next = finalizeThought(next);
    return next;
  }

  if (typ === "koraku.turn_usage") {
    const d = outer.data as Record<string, unknown> | undefined;
    const inTok = typeof d?.input_tokens === "number" ? d.input_tokens : 0;
    const outTok = typeof d?.output_tokens === "number" ? d.output_tokens : 0;
    if (inTok + outTok > 0) {
      next = {
        ...next,
        statusText: `Thinking… · ${inTok + outTok} tok`,
      };
    }
    return next;
  }

  if (typ === "koraku.event") {
    const inner = parseKorakuEventInner(outer.data);
    if (!inner) return next;
    const it = String(inner.type || "").trim();

    if (it === "koraku.trace") {
      const trace = String(inner.trace || "");
      const data = (inner.data || {}) as Record<string, unknown>;
      if (trace === "mode") {
        const mode = data.mode != null ? String(data.mode) : next.mode;
        const max =
          typeof data.max_steps === "number" ? data.max_steps : next.maxSteps;
        const model = data.model != null ? String(data.model) : next.metaModel;
        const provider =
          data.provider != null ? String(data.provider) : next.metaProvider;
        return {
          ...next,
          mode,
          maxSteps: max,
          metaModel: model || next.metaModel,
          metaProvider: provider || next.metaProvider,
          statusText: `${mode} · up to ${max} steps`,
        };
      }
      if (trace === "tools") {
        const tools = Array.isArray(data.tools)
          ? (data.tools as unknown[]).map((x) => String(x))
          : [];
        return { ...next, toolsBadges: tools };
      }
      if (trace === "tool_execution") {
        const tool = String(data.tool || "tool");
        const input = data.input;
        const callId = String(data.id || "");
        const pageTools = new Set([
          "WebPage",
          "WebFetch",
          "Firecrawl",
          "FirecrawlMap",
        ]);
        if (callId && pageTools.has(tool)) {
          const rowId = rid();
          const line = pageToolLine(tool, input, "pending");
          const pendingRow: TimelineRow = {
            id: rowId,
            kind: "tool",
            tool,
            label: line.label,
            detail: line.detail,
            ok: true,
            callId,
          };
          return {
            ...next,
            timeline: [...next.timeline, pendingRow],
            pendingToolByUseId: {
              ...next.pendingToolByUseId,
              [callId]: { tool, input, timelineRowId: rowId },
            },
            toolInvocations: next.toolInvocations + 1,
            statusText: `${tool}…`,
          };
        }
        const { label, detail } = humanizeToolExecution(tool, input);
        const row: TimelineRow = {
          id: rid(),
          kind: "tool",
          tool,
          label,
          detail,
          ok: true,
        };
        return {
          ...next,
          timeline: [...next.timeline, row],
          toolInvocations: next.toolInvocations + 1,
          statusText: `${label}…`,
        };
      }
      return next;
    }

    if (it === "tool_event") {
      return handleToolEvent(next, inner);
    }

    if (it === "stream_event" && inner.event) {
      let ev: Record<string, unknown> | null = null;
      if (typeof inner.event === "string") {
        try {
          ev = JSON.parse(inner.event) as Record<string, unknown>;
        } catch {
          ev = null;
        }
      } else if (typeof inner.event === "object" && inner.event !== null) {
        ev = inner.event as Record<string, unknown>;
      }
      if (!ev) return next;
      return handleStreamEvent(next, ev);
    }

    if (it === "user" && inner.message) {
      return handleUserMessage(next, inner.message as Record<string, unknown>);
    }

    if (it === "system" && inner.subtype === "init") {
      const koraku = inner.koraku as Record<string, unknown> | undefined;
      if (koraku) {
        if (koraku.model) next = { ...next, metaModel: String(koraku.model) };
        if (koraku.provider) {
          next = { ...next, metaProvider: String(koraku.provider) };
        }
        if (koraku.mode != null && koraku.max_steps != null) {
          next = {
            ...next,
            mode: String(koraku.mode),
            maxSteps: Number(koraku.max_steps) || next.maxSteps,
            statusText: `${koraku.mode} · up to ${koraku.max_steps} steps`,
          };
        }
        const tn = koraku.tool_names;
        if (Array.isArray(tn)) {
          next = {
            ...next,
            toolsBadges: tn.map((x) => String(x)),
          };
        }
      }
      return next;
    }

    return next;
  }

  return next;
}
