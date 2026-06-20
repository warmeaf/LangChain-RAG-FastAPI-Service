import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import { marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import { showToast } from 'vant';
import { computed, nextTick, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import 'highlight.js/styles/github.css';
import 'highlight.js/lib/common';
import { useSessionStore } from '../store/session';
import { useUserStore } from '../store/user';

// 配置 marked 高亮插件（只执行一次）
marked.use(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code, lang) {
      const language = hljs.getLanguage(lang) ? lang : 'plaintext';
      return hljs.highlight(code, { language }).value;
    },
  }),
);

/**
 * AI 聊天逻辑封装
 * 提取 AIChat.vue 中的 SSE 流式聊天、消息管理、打字机效果、会话历史加载
 */
export function useChat(messagesContainer) {
  const router = useRouter();
  const route = useRoute();
  const userStore = useUserStore();
  const sessionStore = useSessionStore();

  // 状态
  const messages = ref([
    { role: 'assistant', content: '你好！我是AI助手，有什么可以帮助你的吗？' },
  ]);
  const userInput = ref('');
  const isLoading = ref(false);
  const sessionId = ref('');
  const autoCollapseTimer = ref(null);

  // 计算属性
  const showWelcome = computed(
    () => messages.value.length === 1 && messages.value[0].role === 'assistant',
  );

  // 工具函数
  const formatMessage = (content) => {
    if (!content) return '';
    try {
      const parsed = marked(content, { breaks: true, gfm: true, headerIds: false, mangle: false });
      return DOMPurify.sanitize(parsed);
    } catch {
      return content;
    }
  };

  const truncateText = (text, maxLen) => {
    if (!text) return '';
    return text.length > maxLen ? `${text.slice(0, maxLen)}...` : text;
  };

  // 滚动
  const scrollToBottom = () => {
    if (messagesContainer?.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  };

  // 消息变化自动滚动
  watch(messages, () => nextTick(() => scrollToBottom()), { deep: true });

  // localStorage 降级回退
  const THINKING_HISTORY_KEY = 'ai_thinking_history';
  const loadThinkingFromHistory = (sid) => {
    if (!sid) return null;
    try {
      const history = JSON.parse(localStorage.getItem(THINKING_HISTORY_KEY) || '[]');
      return history.find((e) => e.sessionId === sid)?.thinking || null;
    } catch {
      return null;
    }
  };

  // 思考过程展开/折叠
  const toggleThinking = (message) => {
    message.thinkingCollapsed = !message.thinkingCollapsed;
    if (autoCollapseTimer.value) {
      clearTimeout(autoCollapseTimer.value);
      autoCollapseTimer.value = null;
    }
  };

  // 发送快捷问题
  const sendQuickQuestion = (question) => {
    userInput.value = question;
    sendMessage();
  };

  // 发送消息
  const sendMessage = async () => {
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
    } catch (error) {
      messages.value[messages.value.length - 1].content =
        `发生错误: ${error.message || '请检查网络连接和API设置'}`;
    } finally {
      isLoading.value = false;
      await nextTick();
      scrollToBottom();
    }
  };

  // SSE 流式响应
  const fetchAIResponse = async (userMessage) => {
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
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
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
          const json = JSON.parse(data);

          switch (json.type) {
            case 'step':
              break;

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
                  thinking: [...messages.value[idx].thinking, newStep],
                };
                await nextTick();
                await new Promise((r) => requestAnimationFrame(r));
                scrollToBottom();
              }
              break;
            }

            case 'response': {
              const lastMsg = messages.value[messages.value.length - 1];
              // 第一条 response 到达时自动折叠思考过程
              if (!lastMsg.thinkingAutoCollapsed && lastMsg.thinking.length > 0) {
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
                  await new Promise((r) => setTimeout(r, 0));
                  scrollToBottom();
                  await new Promise((r) => setTimeout(r, 8));
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
        } catch (e) {
          if (e.message && !e.message.includes('API错误')) {
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

  // 重置为欢迎状态
  const resetToWelcome = () => {
    messages.value = [{ role: 'assistant', content: '你好！我是AI助手，有什么可以帮助你的吗？' }];
    sessionId.value = '';
    sessionStore.currentSession = null;
  };

  // 加载会话历史
  const loadSessionHistory = async (session) => {
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

    // 从 API 加载思考过程
    const thinkingData = await sessionStore.getThinking(session.session_id);
    if (thinkingData?.length) {
      let aiIndex = 0;
      for (const msg of messages.value) {
        if (msg.role === 'assistant' && aiIndex < thinkingData.length) {
          msg.thinking = thinkingData[aiIndex];
          aiIndex++;
        }
      }
    } else {
      // API 无数据时回退到 localStorage
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
    formatMessage,
    truncateText,
    toggleThinking,
    sendMessage,
    sendQuickQuestion,
    resetToWelcome,
    loadSessionHistory,
  };
}
