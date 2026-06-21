import { showToast } from 'vant';
import { computed, nextTick, type Ref, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../store/session';
import { useUserStore } from '../store/user';
import type { ChatMessage, SessionData, SseEvent } from '../types';

interface UseChatReturn {
  messages: Ref<ChatMessage[]>;
  userInput: Ref<string>;
  isLoading: Ref<boolean>;
  sessionId: Ref<string>;
  showWelcome: Ref<boolean>;
  toggleThinking: (message: ChatMessage) => void;
  sendMessage: () => Promise<void>;
  sendQuickQuestion: (question: string) => void;
  resetToWelcome: () => void;
  loadSessionHistory: (session: SessionData) => Promise<void>;
}

export function useChat(messagesContainer: Ref<HTMLElement | null>): UseChatReturn {
  const router = useRouter();
  const route = useRoute();
  const userStore = useUserStore();
  const sessionStore = useSessionStore();

  const messages = ref<ChatMessage[]>([]);
  const userInput = ref('');
  const isLoading = ref(false);
  const sessionId = ref('');
  const autoCollapseTimer = ref<ReturnType<typeof setTimeout> | null>(null);

  const showWelcome = computed(() => messages.value.length === 0);

  const scrollToBottom = (): void => {
    if (messagesContainer?.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  };

  watch(messages, () => nextTick(() => scrollToBottom()), { deep: true });

  const THINKING_HISTORY_KEY = 'ai_thinking_history';

  const loadThinkingFromHistory = (sid: string) => {
    if (!sid) return null;
    try {
      const history = JSON.parse(localStorage.getItem(THINKING_HISTORY_KEY) || '[]') as Array<{
        sessionId: string;
        thinking: ChatMessage['thinking'];
      }>;
      return history.find((e) => e.sessionId === sid)?.thinking || null;
    } catch {
      return null;
    }
  };

  const toggleThinking = (message: ChatMessage): void => {
    message.thinkingCollapsed = !message.thinkingCollapsed;
    if (autoCollapseTimer.value) {
      clearTimeout(autoCollapseTimer.value);
      autoCollapseTimer.value = null;
    }
  };

  const sendQuickQuestion = (question: string): void => {
    userInput.value = question;
    sendMessage();
  };

  const sendMessage = async (): Promise<void> => {
    if (!userInput.value.trim() || isLoading.value) return;

    if (!userStore.getLoginStatus) {
      showToast('请先登录');
      return;
    }

    const userMessage = userInput.value.trim();
    messages.value.push({ role: 'user', content: userMessage });
    userInput.value = '';

    messages.value.push({
      role: 'assistant',
      content: '',
      thinking: [],
      thinkingCollapsed: false,
      thinkingAutoCollapsed: false,
    });

    await nextTick();
    scrollToBottom();

    isLoading.value = true;
    try {
      await fetchAIResponse(userMessage);
    } catch (error: unknown) {
      const err = error as { message?: string };
      messages.value[messages.value.length - 1].content =
        `发生错误: ${err.message || '请检查网络连接和API设置'}`;
    } finally {
      isLoading.value = false;
      await nextTick();
      scrollToBottom();
    }
  };

  const fetchAIResponse = async (userMessage: string): Promise<void> => {
    const token = localStorage.getItem('jwt_token') || userStore.token;

    const response = await fetch('/chat/agent/query/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        session_id: sessionId.value || undefined,
        query: userMessage,
      }),
    });

    if (!response.ok) {
      const error = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No reader');

    const decoder = new TextDecoder();
    let buffer = '';
    let aiResponse = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (!data) continue;

        try {
          const json = JSON.parse(data) as SseEvent;

          switch (json.type) {
            case 'thinking': {
              const idx = messages.value.length - 1;
              if (messages.value[idx].role === 'assistant') {
                const newStep = {
                  stage: json.stage || '',
                  content: json.content || '',
                  details: json.details || null,
                };
                messages.value[idx] = {
                  ...messages.value[idx],
                  thinking: [...(messages.value[idx].thinking || []), newStep],
                };
                await nextTick();
                await new Promise<void>((r) => requestAnimationFrame(() => r()));
                scrollToBottom();
              }
              break;
            }

            case 'response': {
              const lastMsg = messages.value[messages.value.length - 1];
              if (!lastMsg.thinkingAutoCollapsed && (lastMsg.thinking?.length || 0) > 0) {
                lastMsg.thinkingAutoCollapsed = true;
                if (autoCollapseTimer.value) clearTimeout(autoCollapseTimer.value);
                autoCollapseTimer.value = setTimeout(() => {
                  lastMsg.thinkingCollapsed = true;
                  autoCollapseTimer.value = null;
                }, 1500);
              }
              const content = json.content || '';
              if (content) {
                aiResponse += content;
                const displayContent = lastMsg.content || '';
                const remainingContent = aiResponse.substring(displayContent.length);
                for (const char of remainingContent) {
                  lastMsg.content += char;
                  await new Promise<void>((r) => setTimeout(r, 0));
                  scrollToBottom();
                  await new Promise<void>((r) => setTimeout(r, 8));
                }
              }
              if (
                json.session_id &&
                typeof json.session_id === 'string' &&
                json.session_id.trim()
              ) {
                sessionId.value = json.session_id;
              }
              break;
            }

            case 'done': {
              const sid = json.session_id;
              if (sid && typeof sid === 'string' && sid.trim()) {
                sessionId.value = sid;
                if (!route.params.sessionId) {
                  router.push(`/aichat/${sid}`);
                }
              }
              break;
            }

            case 'error':
              throw new Error(json.content || 'API错误');
          }
        } catch (e: unknown) {
          const err = e as { message?: string };
          if (err.message && !err.message.includes('API错误')) {
            // Log parse errors but don't throw
          } else {
            throw e;
          }
        }
      }
    }

    if (!aiResponse) {
      messages.value[messages.value.length - 1].content =
        '抱歉，我无法生成回复。请检查API设置或稍后再试。';
    }
  };

  const resetToWelcome = (): void => {
    messages.value = [];
    sessionId.value = '';
    sessionStore.currentSession = null;
  };

  const loadSessionHistory = async (session: SessionData): Promise<void> => {
    if (!session.history?.length) return;

    messages.value = [];
    session.history.forEach(([userMsg, aiMsg]) => {
      messages.value.push({ role: 'user', content: userMsg });
      messages.value.push({
        role: 'assistant',
        content: aiMsg,
        thinking: [],
        thinkingCollapsed: true,
        thinkingAutoCollapsed: true,
      });
    });
    sessionId.value = session.session_id;

    const thinkingData = await sessionStore.getThinking(session.session_id);
    if (thinkingData?.length) {
      let aiIndex = 0;
      for (const msg of messages.value) {
        if (msg.role === 'assistant' && aiIndex < thinkingData.length) {
          msg.thinking = thinkingData[aiIndex] as ChatMessage['thinking'];
          aiIndex++;
        }
      }
    } else {
      const saved = loadThinkingFromHistory(session.session_id);
      if (saved) {
        const last = messages.value[messages.value.length - 1];
        if (last?.role === 'assistant') last.thinking = saved;
      }
    }
  };

  return {
    messages,
    userInput,
    isLoading,
    sessionId,
    showWelcome,
    toggleThinking,
    sendMessage,
    sendQuickQuestion,
    resetToWelcome,
    loadSessionHistory,
  };
}
