const BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function uploadFiles(
  files: File[],
  token: string,
  onProgress: (data: Record<string, unknown>) => void,
) {
  const formData = new FormData();
  for (const f of files) {
    formData.append('files', f);
  }
  const r = await fetch(`${BASE}/knowledge/add/multiple/stream`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  const reader = r.body?.getReader();
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
          onProgress(JSON.parse(line.slice(6)));
        } catch {}
      }
    }
  }
}

export async function getFileList(token: string) {
  const r = await fetch(`${BASE}/knowledge/list`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return r.json();
}

export async function deleteFile(filename: string, token: string) {
  const r = await fetch(
    `${BASE}/knowledge/delete/filename?filename=${encodeURIComponent(filename)}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  return r.json();
}
