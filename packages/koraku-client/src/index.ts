/** Koraku SSE outer event (FastAPI ``text/event-stream``). */
export type KorakuOuterEvent = {
  type: string;
  data?: unknown;
  [key: string]: unknown;
};

export type SlashCommand = {
  name: string;
  description: string;
};

export type KorakuQuestionData = {
  interaction_id?: string;
  run_id?: string;
  questions?: unknown[];
};

export type KorakuApprovalData = {
  interaction_id?: string;
  approval_id?: string;
  run_id?: string;
  tool?: string;
  input?: Record<string, unknown>;
};

export type KorakuActionData = {
  action_id: string;
  label: string;
  description?: string;
  tool: string;
  input?: Record<string, unknown>;
  run_id?: string;
};

export type SystemInitInner = {
  type?: string;
  subtype?: string;
  slash_commands?: SlashCommand[];
  mcp_servers?: Array<{ name: string; command?: string; args?: string[] }>;
  permissionMode?: string;
  tools?: unknown[];
};

export type StreamChatOptions = {
  baseUrl: string;
  message: string;
  sessionId?: string;
  model?: string;
  provider?: string;
  executionTarget?: "cloud" | "local" | "server";
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

export type InteractionRespondBody = {
  interaction_id: string;
  answers?: Record<string, unknown>;
  approved?: boolean;
  updated_input?: Record<string, unknown>;
};

export type ActionExecuteBody = {
  action_id: string;
  overrides?: Record<string, unknown>;
};

/** Parse ``koraku.event`` ``data`` (JSON string or object). */
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

/** Parse one SSE ``data:`` line into a Koraku outer event object. */
export function parseSseDataLine(line: string): KorakuOuterEvent | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) return null;
  const payload = trimmed.slice(5).trim();
  if (!payload || payload === "[DONE]") return null;
  try {
    return JSON.parse(payload) as KorakuOuterEvent;
  } catch {
    return null;
  }
}

export function isKorakuQuestion(event: KorakuOuterEvent): boolean {
  return event.type === "koraku.question";
}

export function isKorakuApproval(event: KorakuOuterEvent): boolean {
  return event.type === "koraku.approval";
}

export function isKorakuAction(event: KorakuOuterEvent): boolean {
  return event.type === "koraku.action";
}

export function isKorakuCompleted(event: KorakuOuterEvent): boolean {
  return event.type === "koraku.completed";
}

export function questionData(event: KorakuOuterEvent): KorakuQuestionData | null {
  if (!isKorakuQuestion(event)) return null;
  return (event.data ?? null) as KorakuQuestionData | null;
}

export function approvalData(event: KorakuOuterEvent): KorakuApprovalData | null {
  if (!isKorakuApproval(event)) return null;
  return (event.data ?? null) as KorakuApprovalData | null;
}

export function actionData(event: KorakuOuterEvent): KorakuActionData | null {
  if (!isKorakuAction(event)) return null;
  return (event.data ?? null) as KorakuActionData | null;
}

/** Extract slash commands from a ``system/init`` inner event. */
export function slashCommandsFromInit(inner: Record<string, unknown>): SlashCommand[] {
  if (inner.subtype !== "init" && inner.type !== "system") return [];
  const raw = inner.slash_commands;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((x): x is SlashCommand => typeof x === "object" && x !== null && "name" in x)
    .map((x) => ({
      name: String((x as SlashCommand).name),
      description: String((x as SlashCommand).description ?? ""),
    }));
}

export function filterSlashCommands(commands: SlashCommand[], query: string): SlashCommand[] {
  const q = query.trim().toLowerCase();
  if (!q) return commands;
  return commands.filter(
    (c) => c.name.toLowerCase().includes(q) || c.description.toLowerCase().includes(q),
  );
}

export async function respondToInteraction(
  baseUrl: string,
  body: InteractionRespondBody,
  headers: Record<string, string> = {},
): Promise<{ ok: boolean }> {
  const url = `${baseUrl.replace(/\/$/, "")}/api/interaction/respond`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Interaction respond failed (${res.status}): ${text || res.statusText}`);
  }
  return res.json() as Promise<{ ok: boolean }>;
}

export async function executeAction(
  baseUrl: string,
  body: ActionExecuteBody,
  headers: Record<string, string> = {},
): Promise<Record<string, unknown>> {
  const url = `${baseUrl.replace(/\/$/, "")}/api/action/execute`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Action execute failed (${res.status}): ${text || res.statusText}`);
  }
  return res.json() as Promise<Record<string, unknown>>;
}

export async function triggerAutomationEvent(
  baseUrl: string,
  eventKey: string,
  payload: Record<string, unknown> | null = null,
  headers: Record<string, string> = {},
): Promise<Record<string, unknown>> {
  const url = `${baseUrl.replace(/\/$/, "")}/api/automations/trigger/${encodeURIComponent(eventKey)}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ payload }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Automation trigger failed (${res.status}): ${text || res.statusText}`);
  }
  return res.json() as Promise<Record<string, unknown>>;
}

/**
 * Stream a chat turn from ``POST /stream``.
 * Yields parsed outer SSE events (`koraku.started`, `koraku.event`, …).
 */
export async function* streamChat(
  options: StreamChatOptions,
): AsyncGenerator<KorakuOuterEvent, void, unknown> {
  const url = `${options.baseUrl.replace(/\/$/, "")}/stream`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(options.headers ?? {}),
    },
    body: JSON.stringify({
      msg: options.message,
      session_id: options.sessionId ?? "",
      model: options.model ?? "",
      provider: options.provider ?? "",
      execution_target: options.executionTarget ?? "local",
    }),
    signal: options.signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Koraku stream failed (${res.status}): ${text || res.statusText}`);
  }
  if (!res.body) {
    throw new Error("Koraku stream response has no body");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        const event = parseSseDataLine(line);
        if (event) yield event;
      }
    }
    if (buffer.trim()) {
      const event = parseSseDataLine(buffer);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}

export class KorakuClient {
  constructor(
    private readonly baseUrl: string,
    private readonly defaultHeaders: Record<string, string> = {},
  ) {}

  streamChat(
    message: string,
    options: Omit<StreamChatOptions, "baseUrl" | "message"> = {},
  ): AsyncGenerator<KorakuOuterEvent, void, unknown> {
    return streamChat({
      baseUrl: this.baseUrl,
      message,
      headers: { ...this.defaultHeaders, ...(options.headers ?? {}) },
      ...options,
    });
  }

  /** Collect inner events from ``koraku.event`` payloads for simple integrations. */
  async *streamInnerEvents(
    message: string,
    options: Omit<StreamChatOptions, "baseUrl" | "message"> = {},
  ): AsyncGenerator<Record<string, unknown>, void, unknown> {
    for await (const outer of this.streamChat(message, options)) {
      if (outer.type === "koraku.event") {
        const inner = parseKorakuEventInner(outer.data);
        if (inner) yield inner;
      }
    }
  }

  /** First ``system/init`` inner event plus slash command list. */
  async streamInit(
    message: string,
    options: Omit<StreamChatOptions, "baseUrl" | "message"> = {},
  ): Promise<{ init: SystemInitInner | null; slashCommands: SlashCommand[] }> {
    let init: SystemInitInner | null = null;
    for await (const outer of this.streamChat(message, options)) {
      if (outer.type === "koraku.event") {
        const inner = parseKorakuEventInner(outer.data);
        if (inner && inner.type === "system" && inner.subtype === "init") {
          init = inner as SystemInitInner;
          return { init, slashCommands: slashCommandsFromInit(inner) };
        }
      }
      if (isKorakuCompleted(outer)) break;
    }
    return { init, slashCommands: init ? slashCommandsFromInit(init as Record<string, unknown>) : [] };
  }

  respondToInteraction(body: InteractionRespondBody) {
    return respondToInteraction(this.baseUrl, body, this.defaultHeaders);
  }

  executeAction(body: ActionExecuteBody) {
    return executeAction(this.baseUrl, body, this.defaultHeaders);
  }

  triggerAutomationEvent(eventKey: string, payload: Record<string, unknown> | null = null) {
    return triggerAutomationEvent(this.baseUrl, eventKey, payload, this.defaultHeaders);
  }
}
