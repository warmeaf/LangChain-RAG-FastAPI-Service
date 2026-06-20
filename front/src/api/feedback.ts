const BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function submitFeedback(
  data: {
    session_id: string;
    query: string;
    feedback_type: 'like' | 'dislike' | 'skip';
    rating?: number;
    clicked_doc_md5?: string;
    clicked_doc_filename?: string;
  },
  token: string,
) {
  const r = await fetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  return r.json();
}

export async function getFeedbackStats(token: string) {
  const r = await fetch(`${BASE}/feedback/stats`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return r.json();
}
