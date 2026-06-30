// ---- User ----
export interface UserInfo {
  uuid?: string;
  id?: number | string;
  user_id?: string;
  username?: string;
  email?: string;
  telephone?: string;
  bio?: string;
  avatar?: string;
  gender?: number;
  create_time?: string;
  last_login?: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegistrationForm {
  username: string;
  email: string;
  telephone: string;
  password: string;
  confirm_password: string;
}

export interface UpdateUserPayload {
  username: string;
  email: string;
  telephone: string;
  gender: number;
  bio: string;
  [key: string]: string | number;
}

// ---- Operation Result ----
export interface OperationResult<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// ---- Session ----
export interface SessionData {
  session_id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  history?: string[][];
}

// ---- Agent Plan / Progress ----
export interface PlanStep {
  id: string;
  tool_name: string;
  reason: string;
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped';
}

export interface AgentPlan {
  steps: PlanStep[];
  total_steps: number;
  replan_count: number;
}

// ---- Chat / Thinking ----
export interface ThinkingStepDetails {
  documents?: Array<{ source: string; score?: number }>;
  scores?: Array<{ rank?: number; index?: number; score: number; preview: string }>;
  hypothetical_doc_preview?: string;
  [key: string]: unknown;
}

export interface ThinkingStep {
  stage: string;
  content: string;
  details: ThinkingStepDetails | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  thinking?: ThinkingStep[];
  thinkingCollapsed?: boolean;
  thinkingAutoCollapsed?: boolean;
  /** Plan-then-Execute Agent 检索计划 */
  plan?: AgentPlan;
}

// ---- Knowledge / Upload ----
export interface UploadProgress {
  filename: string;
  percentage: number;
  status: 'processing' | 'completed' | 'failed';
  message: string;
}

export interface DocumentItem {
  id?: number | string;
  filename: string;
  original_filename?: string;
  chunk_count?: number;
  md5?: string;
  images?: string[];
  content?: string;
  preview?: string;
  created_at?: string;
}

// ---- Action Sheet ----
export interface ActionSheetAction {
  name: string;
  value?: string;
  action?: string;
  color?: string;
}

// ---- SSE Events (new Plan-then-Execute Agent format) ----

export interface SsePlanCreatedEvent {
  type: 'plan_created';
  steps: Array<{ id: string; tool_name: string; reason: string }>;
  total_steps: number;
}

export interface SseStepStartEvent {
  type: 'step_start';
  step_id: string;
  tool_name: string;
  reason: string;
}

export interface SseStepDoneEvent {
  type: 'step_done';
  step_id: string;
  status: 'done' | 'failed' | 'skipped';
}

export interface SseStepReplanEvent {
  type: 'step_replan';
  reason: string;
  new_steps: Array<{ id: string; tool_name: string; tool_args: Record<string, unknown>; reason: string }>;
  new_total_steps: number;
}

export interface SseAnswerStartEvent {
  type: 'answer_start';
}

export interface SseDeltaEvent {
  type: 'delta';
  content: string;
}

export interface SseDoneEvent {
  type: 'done';
  session_id?: string;
}

export interface SseErrorEvent {
  type: 'error';
  content: string;
}

/** Raw thinking event (debug info, preserved for backward tracing) */
export interface SseThinkingEvent {
  type: 'thinking';
  stage: string;
  content: string;
  details: Record<string, unknown> | null;
}

export type SseEvent =
  | SsePlanCreatedEvent
  | SseStepStartEvent
  | SseStepDoneEvent
  | SseStepReplanEvent
  | SseAnswerStartEvent
  | SseDeltaEvent
  | SseDoneEvent
  | SseErrorEvent
  | SseThinkingEvent;
