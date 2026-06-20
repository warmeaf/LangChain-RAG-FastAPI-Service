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

// ---- SSE Events ----
export interface SseThinkingEvent {
  type: 'thinking';
  stage: string;
  content: string;
  details: Record<string, unknown> | null;
}

export interface SseResponseEvent {
  type: 'response';
  content: string;
  session_id?: string;
}

export interface SseDoneEvent {
  type: 'done';
  session_id?: string;
}

export interface SseErrorEvent {
  type: 'error';
  content: string;
}

export type SseEvent = SseThinkingEvent | SseResponseEvent | SseDoneEvent | SseErrorEvent;
