<template>
  <div class="ai-chat-container">
    <van-nav-bar 
      title="AI问答" 
      fixed
      placeholder
    >
      <template #left>
        <span class="nav-sessions-btn" @click="showDrawer = true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </span>
      </template>
    </van-nav-bar>
    
    <div class="chat-content">
      <div class="messages-container" ref="messagesContainer">
        <!-- 欢迎状态（仅首次进入时显示） -->
        <div v-if="showWelcome" class="welcome-card">
          <div class="welcome-icon">
            <van-icon name="service-o" size="36" />
          </div>
          <h3 class="welcome-title">RAG 智能问答</h3>
          <p class="welcome-desc">基于知识库文档的智能问答系统。上传你的文档，开始提问。</p>
          <div class="welcome-questions">
            <button
              v-for="(q, i) in quickQuestions"
              :key="i"
              class="quick-question"
              @click="sendQuickQuestion(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>
        <div 
          v-for="(message, index) in messages" 
          v-show="!showWelcome || message.role === 'user' || index > 0"
          :key="index"
          :class="['message', message.role === 'user' ? 'user-message' : 'ai-message']"
        >
          <div class="message-content">
            <!-- 思考过程区域 -->
            <div v-if="message.thinking && message.thinking.length > 0" class="thinking-section">
              <div class="thinking-header" @click="toggleThinking(message)">
                <span class="thinking-label">💬 思考过程</span>
                <span class="thinking-toggle">{{ message.thinkingCollapsed ? '展开' : '收起' }}</span>
              </div>
              <div v-show="!message.thinkingCollapsed" class="thinking-body">
                <div v-for="(step, sIndex) in message.thinking" :key="sIndex" class="thinking-step">
                  <van-tag :color="getStageColor(step.stage)" size="medium" text-color="var(--van-white)">
                    {{ getStageLabel(step.stage) }}
                  </van-tag>
                  <span class="thinking-step-content">{{ step.content }}</span>
                  <div v-if="step.details" class="thinking-details">
                    <template v-if="step.details.documents">
                      <div v-for="(doc, dIndex) in step.details.documents.slice(0, 3)" :key="dIndex" class="thinking-doc-item">
                        <span class="thinking-doc-source">{{ doc.source }}</span>
                        <span class="thinking-doc-score" v-if="doc.score !== undefined && doc.score !== null">{{ (doc.score * 100).toFixed(0) }}%</span>
                      </div>
                      <div v-if="step.details.documents.length > 3" class="thinking-doc-more">
                        ... 还有 {{ step.details.documents.length - 3 }} 个文档
                      </div>
                    </template>
                    <template v-else-if="step.details.scores">
                      <div v-for="(sc, cIndex) in step.details.scores.slice(0, 3)" :key="cIndex" class="thinking-score-item">
                        <span>#{{ sc.rank || sc.index }}</span>
                        <span>{{ (sc.score * 100).toFixed(0) }}%</span>
                        <span class="thinking-score-preview">{{ truncateText(sc.preview, 40) }}</span>
                      </div>
                    </template>
                    <template v-else-if="step.details.hypothetical_doc_preview">
                      <div class="thinking-detail-text">{{ truncateText(step.details.hypothetical_doc_preview, 80) }}</div>
                    </template>
                    <template v-else>
                      <div v-for="(val, key) in step.details" :key="key" class="thinking-detail-kv">
                        <span class="thinking-detail-key">{{ key }}:</span>
                        <span class="thinking-detail-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
            <!-- 回复正文 -->
            <div v-if="message.content" v-html="formatMessage(message.content)"></div>
            <!-- 打字指示器（无内容且无思考过程时显示） -->
            <div v-if="message.role === 'assistant' && !message.content && (!message.thinking || message.thinking.length === 0)" class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="input-container">
        <van-field
          v-model="userInput"
          rows="1"
          autosize
          type="textarea"
          placeholder="请输入问题..."
          class="chat-input"
          @keypress.enter.prevent="sendMessage"
        />
        <van-button 
          type="primary" 
          class="send-button" 
          :disabled="isLoading || !userInput.trim()" 
          @click="sendMessage"
        >
          发送
        </van-button>
      </div>
    </div>
    
    <tab-bar />
    <SessionDrawer v-model:show="showDrawer" @new-session="resetToWelcome" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import TabBar from '../components/TabBar.vue';
import SessionDrawer from '../components/SessionDrawer.vue';
import { showToast } from 'vant';
import { marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css';
import 'highlight.js/lib/common';
import { apiConfig } from '../config/api';
import { useUserStore } from '../store/user';
import { useSessionStore } from '../store/session';

// 从cookie中获取CSRF token
const getCsrfToken = () => {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue || '';
};

// 聊天消息
const messages = ref([
  { role: 'assistant', content: '你好！我是AI助手，有什么可以帮助你的吗？' }
]);
const userInput = ref('');
const messagesContainer = ref(null);
const isLoading = ref(false);
const sessionId = ref('');
const hasJumped = ref(false);
const autoCollapseTimer = ref(null);
const showDrawer = ref(false);

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();
const sessionStore = useSessionStore();

// 欢迎状态：没有任何用户消息时显示
const showWelcome = computed(() => {
  return messages.value.length === 1 && messages.value[0].role === 'assistant';
});

// 快捷提问
const quickQuestions = [
  '给我讲个笑话',
  '介绍一下 RAG 技术',
  '你能帮我做什么？',
  '如何开始使用？',
];

const sendQuickQuestion = (question) => {
  userInput.value = question;
  sendMessage();
};

// 配置marked使用marked-highlight插件
marked.use(markedHighlight({
  langPrefix: 'hljs language-',
  highlight(code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
    return hljs.highlight(code, { language }).value;
  }
}));

// 格式化消息内容（支持Markdown和代码高亮）
const formatMessage = (content) => {
  if (!content) return '';
  try {
    // 使用marked解析Markdown，并用DOMPurify清理HTML
    const parsed = marked(content, {
      breaks: true,
      gfm: true,
      headerIds: false,
      mangle: false
    });
    const sanitized = DOMPurify.sanitize(parsed);
    return sanitized;
  } catch (error) {
    console.error('Markdown解析错误:', error);
    return content;
  }
};

// 思考过程阶段配置（温润色调）
const stageConfig = {
  retrieval:  { label: '检索',   color: '#B8926E' },
  hyde:       { label: 'HyDE',   color: '#8B7E6F' },
  reorder:    { label: '重排序', color: '#D4914A' },
  summarize:  { label: '总结',   color: '#7D9B7A' }
};

const getStageLabel = (stage) => {
  return stageConfig[stage]?.label || stage || '处理中';
};

const getStageColor = (stage) => {
  return stageConfig[stage]?.color || '#999';
};

const truncateText = (text, maxLen) => {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
};

// localStorage 存储（保留读取作为降级回退）
const THINKING_HISTORY_KEY = 'ai_thinking_history';

const loadThinkingFromHistory = (sessionId) => {
  if (!sessionId) return null;
  try {
    const history = JSON.parse(localStorage.getItem(THINKING_HISTORY_KEY) || '[]');
    return history.find(e => e.sessionId === sessionId)?.thinking || null;
  } catch (e) {
    return null;
  }
};

// 切换思考过程展开/折叠（用户手动操作时取消自动折叠定时器）
const toggleThinking = (message) => {
  message.thinkingCollapsed = !message.thinkingCollapsed;
  if (autoCollapseTimer.value) {
    clearTimeout(autoCollapseTimer.value);
    autoCollapseTimer.value = null;
  }
};

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim() || isLoading.value) return;
  
  // 检查是否登录
  if (!userStore.getLoginStatus) {
    showToast('请先登录');
    return;
  }
  
  // 添加用户消息
  const userMessage = userInput.value.trim();
  messages.value.push({ role: 'user', content: userMessage });
  userInput.value = '';
  
  // 添加AI消息占位（含思考过程字段）
  messages.value.push({ role: 'assistant', content: '', thinking: [], thinkingCollapsed: false, thinkingAutoCollapsed: false });
  
  // 滚动到底部
  await nextTick();
  scrollToBottom();
  
  // 发送请求
  isLoading.value = true;
  try {
    await fetchAIResponse(userMessage);
  } catch (error) {
    console.error('Error fetching AI response:', error);
    // 更新最后一条消息为错误信息
    messages.value[messages.value.length - 1].content = `发生错误: ${error.message || '请检查网络连接和API设置'}`;
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
};

// 获取AI响应（使用SSE）
const fetchAIResponse = async (userMessage) => {
  try {
    // 确保使用正确的相对路径，通过Vite代理访问
    const url = '/chat/agent/query/stream';
    // 从localStorage获取token
    const token = localStorage.getItem('jwt_token') || userStore.token;
    // console.log('发送AI请求到:', url);
    // console.log('使用的token:', token);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        session_id: sessionId.value || undefined,
        query: userMessage
      })
    });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    
    // 处理SSE流
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
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (!data) continue;
        
        try {
          const json = JSON.parse(data);
          
          switch (json.type) {
            case 'step':
              break;
            case 'thinking':
              {
                const idx = messages.value.length - 1;
                if (messages.value[idx].role === 'assistant') {
                  const newStep = {
                    stage: json.stage || '',
                    content: json.content || '',
                    details: json.details || null
                  };
                  // 完整替换消息对象以强制 Vue 重新渲染
                  messages.value[idx] = {
                    ...messages.value[idx],
                    thinking: [...messages.value[idx].thinking, newStep]
                  };
                  // 等待 Vue DOM 刷新 + 浏览器 paint
                  await nextTick();
                  await new Promise(resolve => requestAnimationFrame(resolve));
                  scrollToBottom();
                }
              }
              break;
            case 'response':
              {
                const lastMsg = messages.value[messages.value.length - 1];
                // 第一条 response 到达时延迟折叠思考过程（仅一次）
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
                  
                  // 逐字符显示打字机效果
                  const displayContent = lastMsg.content || '';
                  const remainingContent = aiResponse.substring(displayContent.length);
                  
                  for (const char of remainingContent) {
                    lastMsg.content += char;
                  await new Promise(resolve => setTimeout(resolve, 0));
                    scrollToBottom();
                    // 控制打字速度，每个字符延迟8ms
                    await new Promise(resolve => setTimeout(resolve, 8));
                  }
                }
                // 保存会话ID（不立即跳转，避免中断SSE）
                if (json.session_id && typeof json.session_id === 'string' && json.session_id.trim()) {
                  sessionId.value = json.session_id;
                }
              }
              break;
            case 'done':
              {
                const sid = json.session_id;
                if (sid && typeof sid === 'string' && sid.trim()) {
                  sessionId.value = sid;
                  // 如果当前路由没有sessionId参数，跳转到带sessionId的路由
                  if (!route.params.sessionId) {
                    router.push(`/aichat/${sid}`);
                  }
                }
              }
              break;
            case 'error':
              throw new Error(json.content || 'API错误');
              break;
          }
        } catch (e) {
          console.error('Error parsing SSE data:', e);
        }
      }
    }
  }
  
  // 如果没有收到任何内容
  if (!aiResponse) {
    messages.value[messages.value.length - 1].content = '抱歉，我无法生成回复。请检查API设置或稍后再试。';
  }
  } catch (error) {
    console.error('Fetch error:', error);
    throw error;
  }
};

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// 重置为欢迎状态
const resetToWelcome = () => {
  messages.value = [
    { role: 'assistant', content: '你好！我是AI助手，有什么可以帮助你的吗？' }
  ];
  sessionId.value = '';
  sessionStore.currentSession = null;
};

// 监听消息变化，自动滚动
watch(messages, () => {
  nextTick(() => {
    scrollToBottom();
  });
}, { deep: true });

// 监听路由参数变化，重新加载会话历史
watch(() => route.params.sessionId, async (newSessionId) => {
  if (newSessionId) {
    try {
      const result = await sessionStore.getSession(newSessionId);
      if (result.success && sessionStore.currentSession) {
        await loadSessionHistory(sessionStore.currentSession);
      } else {
        showToast('加载会话历史失败');
      }
    } catch (error) {
      console.error('加载会话历史失败:', error);
      showToast('加载会话历史失败');
    }
  }
}, { immediate: true });

// 组件挂载时检查是否有当前会话或路由参数中的会话ID
onMounted(async () => {
  // 检查路由参数中是否有sessionId
  const routeSessionId = route.params.sessionId;
  
  if (routeSessionId) {
    // 从路由参数获取会话ID，加载会话历史
    try {
      const result = await sessionStore.getSession(routeSessionId);
      if (result.success && sessionStore.currentSession) {
        await loadSessionHistory(sessionStore.currentSession);
      } else {
        showToast('加载会话历史失败');
      }
    } catch (error) {
      console.error('加载会话历史失败:', error);
      showToast('加载会话历史失败');
    }
  } else if (sessionStore.currentSession) {
    // 从store中加载会话历史
    await loadSessionHistory(sessionStore.currentSession);
  }
  
  scrollToBottom();
});

// 加载会话历史（异步，从 API 加载思考过程）
const loadSessionHistory = async (session) => {
  if (session.history && session.history.length > 0) {
    // 清空当前消息
    messages.value = [];
    // 加载历史消息
    session.history.forEach(([userMsg, aiMsg]) => {
      messages.value.push({ role: 'user', content: userMsg });
      messages.value.push({ role: 'assistant', content: aiMsg, thinking: [], thinkingCollapsed: true, thinkingAutoCollapsed: true });
    });
    // 设置会话ID
    sessionId.value = session.session_id;

    // 从 API 加载思考过程
    const thinkingData = await sessionStore.getThinking(session.session_id);
    if (thinkingData && thinkingData.length > 0) {
      // 按索引将 thinking[i] 分配到第 i 个 assistant 消息
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
      if (saved && messages.value.length > 0) {
        const last = messages.value[messages.value.length - 1];
        if (last.role === 'assistant') {
          last.thinking = saved;
        }
      }
    }
  }
};
</script>
