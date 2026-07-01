import { showToast } from 'vant';
import { computed, nextTick, type Ref, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../store/session';
import { useUserStore } from '../store/user';
import type { AgentPlan, ChatMessage, PlanStep, SessionData, SseEvent } from '../types';

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

/** 工具名 → 中文标签映射 */
const TOOL_LABELS: Record<string, string> = {
  vector_search: '向量检索',
  keyword_search: '关键词检索',
  sql_query: 'SQL 查询',
  metadata_filter_milvus: '元数据过滤',
  get_weather: '天气查询',
  get_current_time: '时间查询',
  ocr_recognize: 'OCR 识别',
};

function toolLabel(name: string): string {
  return TOOL_LABELS[name] || name;
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

  /** 获取最后一条 assistant 消息 */
  const lastAssistant = (): ChatMessage | null => {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'assistant') return messages.value[i];
    }
    return null;
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
      plan: undefined,
    });

    await nextTick();
    scrollToBottom();

    isLoading.value = true;
    try {
      await fetchAIResponse(userMessage);
    } catch (error: unknown) {
      const err = error as { message?: string };
      const last = lastAssistant();
      if (last) last.content = `发生错误: ${err.message || '请检查网络连接和API设置'}`;
    } finally {
      isLoading.value = false;
      await nextTick();
      scrollToBottom();
    }
  };

  const fetchAIResponse = async (_userMessage: string): Promise<void> => {
    const token = localStorage.getItem('jwt_token') || userStore.token;

    const response = await fetch('/chat/agent/query/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        session_id: sessionId.value || undefined,
        query: _userMessage,
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
    let answerStarted = false;

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
            // ── 计划创建 ──
            case 'plan_created': {
              const msg = lastAssistant();
              if (msg) {
                msg.plan = {
                  steps: json.steps.map((s) => ({
                    id: s.id,
                    tool_name: s.tool_name,
                    reason: s.reason,
                    status: 'pending' as const,
                  })),
                  total_steps: json.total_steps,
                  replan_count: 0,
                };
              }
              break;
            }

            // ── 步骤开始 ──
            case 'step_start': {
              const msg = lastAssistant();
              if (msg?.plan) {
                const step = msg.plan.steps.find((s) => s.id === json.step_id);
                if (step) step.status = 'running';
              } else {
                // 无 plan 时，插入 thinking 条目供 ThinkingSteps 渲染
                if (msg) {
                  msg.thinking = [...(msg.thinking || []), {
                    stage: 'step_start',
                    content: `调用 ${toolLabel(json.tool_name)}: ${json.reason || ''}`,
                    details: {
                      step_id: json.step_id,
                      tool_name: json.tool_name,
                      reason: json.reason,
                    },
                  }];
                  await nextTick();
                  await new Promise<void>((r) => requestAnimationFrame(() => r()));
                  scrollToBottom();
                }
              }
              break;
            }

            // ── 步骤完成 ──
            case 'step_done': {
              const msg = lastAssistant();
              if (msg?.plan) {
                const step = msg.plan.steps.find((s) => s.id === json.step_id);
                if (step) step.status = json.status as PlanStep['status'];
              } else {
                // 无 plan 时，插入 thinking 条目
                if (msg) {
                  const statusText = { done: '完成', failed: '失败', skipped: '跳过' }[json.status] || json.status;
                  msg.thinking = [...(msg.thinking || []), {
                    stage: 'step_done',
                    content: `步骤完成: ${toolLabel(json.step_id)} (${statusText})`,
                    details: {
                      step_id: json.step_id,
                      status: json.status,
                    },
                  }];
                  await nextTick();
                  await new Promise<void>((r) => requestAnimationFrame(() => r()));
                  scrollToBottom();
                }
              }
              break;
            }

            // ── 计划修正 ──
            case 'step_replan': {
              const msg = lastAssistant();
              if (msg?.plan) {
                // 保留已完成的步骤，替换为新步骤
                const completed = msg.plan.steps.filter(
                  (s) => s.status === 'done' || s.status === 'failed'
                );
                const newSteps: PlanStep[] = json.new_steps.map((s) => ({
                  id: s.id,
                  tool_name: s.tool_name,
                  reason: s.reason,
                  status: 'pending' as const,
                }));
                msg.plan.steps = [...completed, ...newSteps];
                msg.plan.total_steps = json.new_total_steps;
                msg.plan.replan_count++;
              }
              break;
            }

            // ── 回答开始 ──
            case 'answer_start': {
              answerStarted = true;
              const msg = lastAssistant();
              if (msg && (msg.thinking?.length || 0) > 0) {
                msg.thinkingAutoCollapsed = true;
                if (autoCollapseTimer.value) clearTimeout(autoCollapseTimer.value);
                autoCollapseTimer.value = setTimeout(() => {
                  msg.thinkingCollapsed = true;
                  autoCollapseTimer.value = null;
                }, 1500);
              }
              break;
            }

            // ── 回答文本增量 ──
            case 'delta': {
              const content = json.content || '';
              if (!content) break;
              aiResponse += content;

              // 首次 delta 视为隐式 answer_start
              if (!answerStarted) {
                answerStarted = true;
                const msg = lastAssistant();
                if (msg && (msg.thinking?.length || 0) > 0) {
                  msg.thinkingAutoCollapsed = true;
                  if (autoCollapseTimer.value) clearTimeout(autoCollapseTimer.value);
                  autoCollapseTimer.value = setTimeout(() => {
                    msg.thinkingCollapsed = true;
                    autoCollapseTimer.value = null;
                  }, 1500);
                }
              }

              const last = lastAssistant();
              if (last) {
                const displayContent = last.content || '';
                const remainingContent = aiResponse.substring(displayContent.length);
                for (const char of remainingContent) {
                  last.content += char;
                  await new Promise<void>((r) => setTimeout(r, 0));
                  scrollToBottom();
                  await new Promise<void>((r) => setTimeout(r, 8));
                }
              }
              break;
            }

            // ── 思考事件（保留用于调试）──
            case 'thinking': {
              const msg = lastAssistant();
              if (msg) {
                const newStep = {
                  stage: json.stage || '',
                  content: json.content || '',
                  details: json.details || null,
                };
                msg.thinking = [...(msg.thinking || []), newStep];
                await nextTick();
                await new Promise<void>((r) => requestAnimationFrame(() => r()));
                scrollToBottom();
              }
              break;
            }

            // ── 流结束 ──
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

            // ── 错误 ──
            case 'error':
              throw new Error(json.content || 'API错误');
          }
        } catch (e: unknown) {
          const err = e as { message?: string };
          if (err.message && !err.message.includes('API错误')) {
            // 解析错误不抛
          } else {
            throw e;
          }
        }
      }
    }

    if (!aiResponse) {
      const last = lastAssistant();
      if (last) last.content = '抱歉，我无法生成回复。请检查API设置或稍后再试。';
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

    // 加载 thinking 事件
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
        const last = lastAssistant();
        if (last) last.thinking = saved;
      }
    }

    // 加载检索计划（Plan-then-Execute Agent）
    try {
      const planResp = await fetch(
        `${import.meta.env.VITE_API_BASE_URL || ''}/chat/session/${session.session_id}/plan`,
        { headers: { Authorization: `Bearer ${userStore.token}` } }
      );
      if (planResp.ok) {
        const planJson = await planResp.json();
        const plan = planJson?.data?.plan;
        if (plan) {
          const last = lastAssistant();
          if (last) last.plan = plan;
        }
      }
    } catch {
      // plan 加载失败不影响主流程
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
