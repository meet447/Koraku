/** Koraku HTTP SSE outer event types (``koraku.*`` envelope). */
export const KorakuSseType = {
  started: "koraku.started",
  event: "koraku.event",
  question: "koraku.question",
  approval: "koraku.approval",
  action: "koraku.action",
  completed: "koraku.completed",
  error: "koraku.error",
} as const;

export type KorakuSseTypeName = (typeof KorakuSseType)[keyof typeof KorakuSseType];

/** Inner agent event types (inside ``koraku.event`` payloads). */
export const AgentEventType = {
  completed: "agent.completed",
  question: "agent.question",
  approval: "agent.approval",
  error: "agent.error",
  action: "agent.action",
  streamEvent: "stream_event",
  subagent: "agent.subagent",
} as const;

export type SlashCommand = {
  name: string;
  description: string;
};

export type QuestionOption = {
  label: string;
  description?: string;
  preview?: string;
};

export type Question = {
  header: string;
  question: string;
  text?: string;
  options?: QuestionOption[] | string[];
  multiSelect?: boolean;
};

export type KorakuQuestionData = {
  interaction_id?: string;
  question_id?: string;
  run_id?: string;
  questions?: Question[];
};

export type KorakuApprovalData = {
  interaction_id?: string;
  approval_id?: string;
  run_id?: string;
  tool?: string;
  input?: Record<string, unknown>;
  tool_use_id?: string;
};

export type KorakuActionData = {
  action_id: string;
  label: string;
  description?: string;
  tool: string;
  input?: Record<string, unknown>;
  run_id?: string;
};

export type KorakuCompletedData = {
  reason?: string;
  steps?: number;
  mode?: string;
  provider?: string;
  model?: string;
  run_id?: string;
};

export type KorakuErrorData = {
  error?: string;
  code?: string;
  run_id?: string;
};

export type KorakuOuterEventBase = {
  type: string;
  data?: unknown;
};

export type KorakuQuestionEvent = KorakuOuterEventBase & {
  type: typeof KorakuSseType.question;
  data?: KorakuQuestionData;
};

export type KorakuApprovalEvent = KorakuOuterEventBase & {
  type: typeof KorakuSseType.approval;
  data?: KorakuApprovalData;
};

export type KorakuActionEvent = KorakuOuterEventBase & {
  type: typeof KorakuSseType.action;
  data?: KorakuActionData;
};

export type KorakuCompletedEvent = KorakuOuterEventBase & {
  type: typeof KorakuSseType.completed;
  data?: KorakuCompletedData;
};

export type KorakuErrorEvent = KorakuOuterEventBase & {
  type: typeof KorakuSseType.error;
  data?: KorakuErrorData;
};

export type KorakuOuterEvent =
  | KorakuQuestionEvent
  | KorakuApprovalEvent
  | KorakuActionEvent
  | KorakuCompletedEvent
  | KorakuErrorEvent
  | KorakuOuterEventBase;

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
  executionTarget?: "sandbox" | "local" | "server";
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

export type InteractionRespondBody = {
  interaction_id: string;
  answers?: Record<string, string>;
  approved?: boolean;
  updated_input?: Record<string, unknown>;
};

export type ActionExecuteBody = {
  action_id: string;
  overrides?: Record<string, unknown>;
};
