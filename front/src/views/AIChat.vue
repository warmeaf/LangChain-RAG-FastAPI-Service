<template>
  <div>
    <van-nav-bar 
      title="AI问答" 
      fixed
      placeholder
    >
      <template #left>
        <span @click="showDrawer = true">
          <History :size="18" />
        </span>
      </template>
    </van-nav-bar>
    
    <div class="flex flex-col" style="height: calc(100dvh - 46px - 50px)">
      <div ref="messagesContainer" class="flex-1 overflow-y-auto px-[var(--van-padding-xs)] py-[var(--van-padding-xs)]" style="scrollbar-gutter: stable">
        <!-- 欢迎状态（仅首次进入时显示） -->
        <div v-if="showWelcome" class="flex flex-col items-center justify-center gap-[var(--van-padding-lg)] py-12">
          <div class="flex items-center justify-center w-16 h-16 bg-blue-50 rounded-full">
            <Bot :size="32" color="var(--van-blue)" />
          </div>
          <h3 class="m-0 text-[var(--van-font-size-lg)] font-semibold">RAG 智能问答</h3>
          <p class="m-0 text-[var(--van-font-size-md)] text-[var(--van-text-color-2)] text-center px-[var(--van-padding-md)]">基于知识库文档的智能问答系统。上传你的文档，开始提问。</p>
          <div class="flex flex-wrap justify-center gap-[var(--van-padding-xs)]">
            <van-button
              v-for="(q, i) in quickQuestions"
              :key="i"
              size="small"
              plain
              hairline
              @click="sendQuickQuestion(q)"
            >
              {{ q }}
            </van-button>
          </div>
        </div>
        <div
          v-for="(message, index) in messages"
          v-show="!showWelcome || message.role === 'user' || index > 0"
          :key="index"
          :class="['flex mb-[var(--van-padding-sm)]', message.role === 'user' ? 'justify-end' : 'justify-start']"
        >
          <div :class="[
              message.role === 'user'
                ? 'w-fit max-w-[85%] bg-[var(--van-primary-color)] text-[var(--van-white)] rounded-[var(--van-radius-lg)] px-[var(--van-padding-xs)] py-[var(--van-padding-xs)]'
                : message.thinking && message.thinking.length > 0
                  ? 'w-full max-w-[85%] bg-[var(--van-gray-3)] border border-[var(--van-border-color)] rounded-[var(--van-radius-lg)] px-[var(--van-padding-xs)] py-[var(--van-padding-xs)]'
                  : 'w-fit max-w-[85%] bg-[var(--van-gray-3)] border border-[var(--van-border-color)] rounded-[var(--van-radius-lg)] px-[var(--van-padding-xs)] py-[var(--van-padding-xs)]'
            ]">
            <!-- 思考过程区域 -->
            <ThinkingSteps
              :thinking="message.thinking || []"
              :collapsed="message.thinkingCollapsed || false"
              @toggle="toggleThinking(message)"
            />
            <!-- 回复正文 -->
            <div v-if="message.content" class="text-[var(--van-font-size-md)] leading-relaxed">
              <MarkdownRender custom-id="chat" :content="message.content" :typewriter="false" :fade="false" />
            </div>
            <!-- 打字指示器（无内容且无思考过程时显示） -->
            <div v-if="message.role === 'assistant' && !message.content && (!message.thinking || message.thinking.length === 0)"
              class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>
      
      <van-cell-group inset class="mb-[var(--van-padding-sm)]!">
      <van-cell center class="shadow-sm!" :border="false">
        <template #title>
          <van-field
            v-model="userInput"
            rows="1"
            autosize
            type="textarea"
            placeholder="请输入问题..."
            :border="false"
            class="flex-1!"
            @keypress.enter.prevent="sendMessage"
          />
        </template>
        <template #right-icon>
          <van-button
            type="primary"
            size="mini"
            :disabled="isLoading || !userInput.trim()"
            class="w-9! h-9! p-0! min-w-0! shrink-0"
          @click="sendMessage"
        >
            <Send :size="16" color="currentColor" />
          </van-button>
        </template>
      </van-cell>
      </van-cell-group>
    </div>
    
    <tab-bar />
    <SessionDrawer v-model:show="showDrawer" @new-session="resetToWelcome" />
  </div>
</template>

<script setup lang="ts">
import { Bot, History, Send } from '@lucide/vue';
import MarkdownRender from 'markstream-vue';
import { showToast } from 'vant';
import { onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import ThinkingSteps from '../components/chat/ThinkingSteps.vue';
import SessionDrawer from '../components/SessionDrawer.vue';
import TabBar from '../components/TabBar.vue';
import { useChat } from '../composables/useChat';
import { useSessionStore } from '../store/session';

const route = useRoute();
const sessionStore = useSessionStore();

const messagesContainer = ref<HTMLElement | null>(null);
const showDrawer = ref(false);

	const {
	  messages, userInput, isLoading, sessionId, showWelcome,
	  toggleThinking,
	  sendMessage, sendQuickQuestion, resetToWelcome, loadSessionHistory,
	} = useChat(messagesContainer);

// 快捷提问
const quickQuestions = [
  '给我讲个笑话',
  '介绍一下 RAG 技术',
  '你能帮我做什么？',
  '如何开始使用？',
];

// 监听路由参数变化，加载会话历史
watch(() => route.params.sessionId, async (newSessionId) => {
  if (newSessionId) {
    try {
      const result = await sessionStore.getSession(newSessionId as string);
      if (result.success && sessionStore.currentSession) {
        await loadSessionHistory(sessionStore.currentSession);
      } else {
        showToast('加载会话历史失败');
      }
    } catch {
      showToast('加载会话历史失败');
    }
  }
}, { immediate: true });

// 组件挂载时加载会话
onMounted(async () => {
  const routeSessionId = route.params.sessionId;
  if (routeSessionId) {
    try {
      const result = await sessionStore.getSession(routeSessionId as string);
      if (result.success && sessionStore.currentSession) {
        await loadSessionHistory(sessionStore.currentSession);
      } else {
        showToast('加载会话历史失败');
      }
    } catch {
      showToast('加载会话历史失败');
    }
  } else if (sessionStore.currentSession) {
    await loadSessionHistory(sessionStore.currentSession);
  }
});
</script>

<style scoped>
/* 打字指示器波浪动画 */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 0;
}
.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--van-gray-5);
  animation: typing-wave 1.2s ease-in-out infinite;
}
.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}
.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes typing-wave {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-6px);
    opacity: 1;
  }
}
</style>
