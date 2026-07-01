const BASE = import.meta.env.VITE_API_BASE_URL || '';

/** SSE 事件回调 */
export interface ChatCallbacks {
  onPlanUpdated?: (data: { steps: Array<{ id: string; content: string; status: string }>; total_steps: number }) => void;
  onStepStart?: (data: { step_id: string; tool_name: string; reason: string }) => void;
  onStepDone?: (data: { step_id: string; status: 'done' | 'failed' | 'skipped' }) => void;
  onAnswerStart?: () => void;
  onDelta?: (text: string) => void;
  onThinking?: (data: { stage: string; content: string; details: Record<string, unknown> | null }) => void;
  onDone?: (sessionId?: string) => void;
  onError?: (err: string) => void;
}

export async function sendChatMessage(
  query: string,
  sessionId: string,
  token: string,
  callbacks: ChatCallbacks,
) {
  const response = await fetch(`${BASE}/chat/agent/query/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query, session_id: sessionId }),
  });

  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          switch (data.type) {
            case 'plan_updated': callbacks.onPlanUpdated?.(data); break;
            case 'step_start': callbacks.onStepStart?.(data); break;
            case 'step_done': callbacks.onStepDone?.(data); break;
            case 'answer_start': callbacks.onAnswerStart?.(); break;
            case 'delta': callbacks.onDelta?.(data.content); break;
            case 'thinking': callbacks.onThinking?.(data); break;
            case 'done': callbacks.onDone?.(data.session_id); break;
            case 'error': callbacks.onError?.(data.content); break;
          }
        } catch {
          // skip parse errors
        }
      }
    }
  }
}
