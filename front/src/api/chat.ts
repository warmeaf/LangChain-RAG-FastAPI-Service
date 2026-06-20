const BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function sendChatMessage(
  query: string,
  sessionId: string,
  token: string,
  onThinking: (data: any) => void,
  onText: (text: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
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
          if (data.type === 'thinking') onThinking(data);
          else if (data.type === 'text') onText(data.content);
          else if (data.type === 'done') onDone();
          else if (data.type === 'error') onError(data.content);
        } catch {}
      }
    }
  }
}
