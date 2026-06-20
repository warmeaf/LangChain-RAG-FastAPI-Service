import axios from 'axios';
import { defineStore } from 'pinia';
import type { OperationResult, SessionData } from '../types';

interface SessionState {
  sessions: SessionData[];
  currentSession: SessionData | null;
  loading: boolean;
}

interface SessionListApiResponse {
  data: {
    data?: {
      sessions?: Array<{
        id: string;
        title: string;
        created_at: string;
        updated_at: string;
      }>;
    };
  };
}

interface SessionDetailApiResponse {
  data: {
    data?: SessionData;
  };
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    sessions: [],
    currentSession: null,
    loading: false,
  }),

  getters: {
    getSessions: (state: SessionState): SessionData[] => state.sessions,
    getCurrentSession: (state: SessionState): SessionData | null => state.currentSession,
    isLoading: (state: SessionState): boolean => state.loading,
  },

  actions: {
    async getUserSessions(userId: string | number): Promise<OperationResult<SessionData[]>> {
      try {
        this.loading = true;
        const token = localStorage.getItem('jwt_token');

        const response = await axios.get<SessionListApiResponse['data']>(
          `/chat/sessions/${userId}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );

        const sessionsData = response.data.data?.sessions || [];

        this.sessions = sessionsData.map((session) => ({
          session_id: session.id,
          title: session.title,
          created_at: session.created_at,
          updated_at: session.updated_at,
        }));

        this.sessions.sort((a, b) => {
          const dateA = new Date(a.updated_at || a.created_at || 0);
          const dateB = new Date(b.updated_at || b.created_at || 0);
          return dateB.getTime() - dateA.getTime();
        });

        return { success: true, data: this.sessions };
      } catch (error: unknown) {
        const err = error as { response?: { data?: { detail?: string } } };
        return { success: false, message: err.response?.data?.detail || '获取会话失败' };
      } finally {
        this.loading = false;
      }
    },

    async getSession(sessionId: string): Promise<OperationResult<SessionData>> {
      try {
        this.loading = true;
        const token = localStorage.getItem('jwt_token');

        const response = await axios.get<SessionDetailApiResponse['data']>(
          `/chat/session/${sessionId}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );

        const sessionData = response.data.data || response.data;
        this.currentSession = sessionData as SessionData;
        return { success: true, data: sessionData as SessionData };
      } catch (error: unknown) {
        const err = error as { response?: { data?: { detail?: string } } };
        return { success: false, message: err.response?.data?.detail || '获取会话详情失败' };
      } finally {
        this.loading = false;
      }
    },

    async deleteSession(sessionId: string): Promise<OperationResult> {
      try {
        this.loading = true;
        const token = localStorage.getItem('jwt_token');

        await axios.delete(`/chat/session/${sessionId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (Array.isArray(this.sessions)) {
          this.sessions = this.sessions.filter((s) => s.session_id !== sessionId);
        } else {
          this.sessions = [];
        }

        if (this.currentSession?.session_id === sessionId) {
          this.currentSession = null;
        }

        return { success: true, message: '会话删除成功' };
      } catch (error: unknown) {
        const err = error as { response?: { data?: { detail?: string } } };
        return { success: false, message: err.response?.data?.detail || '删除会话失败' };
      } finally {
        this.loading = false;
      }
    },

    async createSession(query: string): Promise<OperationResult<SessionData>> {
      try {
        this.loading = true;
        const token = localStorage.getItem('jwt_token');

        const response = await fetch('/chat/agent/query/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ query }),
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({}) as Record<string, string>);
          throw new Error(
            (error as { detail?: string }).detail || `HTTP error! status: ${response.status}`,
          );
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('无法读取响应流');

        const decoder = new TextDecoder();
        let buffer = '';
        let sessionId: string | null = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (!data) continue;

              try {
                const json = JSON.parse(data) as { session_id?: string };
                if (json.session_id) {
                  sessionId = json.session_id;
                  break;
                }
              } catch {
                // skip non-JSON data lines
              }
            }
          }

          if (sessionId) break;
        }

        if (sessionId) {
          const sessionResponse = await this.getSession(sessionId);
          return sessionResponse;
        }
        throw new Error('创建会话失败，未获取到会话ID');
      } catch (error: unknown) {
        const err = error as { message?: string };
        return { success: false, message: err.message || '创建会话失败' };
      } finally {
        this.loading = false;
      }
    },

    async getThinking(sessionId: string): Promise<unknown[]> {
      try {
        const token = localStorage.getItem('jwt_token');
        const response = await axios.get<{ data?: { data?: { thinking?: unknown[] } } }>(
          `/chat/session/${sessionId}/thinking`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        return response.data.data?.data?.thinking || [];
      } catch {
        return [];
      }
    },

    setCurrentSession(session: SessionData): void {
      this.currentSession = session;
    },

    clearSessions(): void {
      this.sessions = [];
      this.currentSession = null;
    },
  },
});
