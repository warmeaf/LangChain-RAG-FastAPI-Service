<template>
  <van-popup
    :show="show"
    position="left"
    :style="{ width: '85%', height: '100%' }"
    @update:show="$emit('update:show', $event)"
  >
    <div class="drawer-container">
      <!-- 头部 -->
      <div class="drawer-header">
        <div class="header-title">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <span>历史会话</span>
        </div>
        <van-button size="small" type="primary" @click="createNewSession">新会话</van-button>
      </div>

      <!-- 内容 -->
      <div class="drawer-content">
        <div v-if="sessionStore.isLoading" class="loading">
          <van-loading type="spinner" color="#1989fa" />
          <p>加载中...</p>
        </div>

        <div v-else-if="sessionStore.sessions.length === 0" class="empty-sessions">
          <div class="empty-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              <line x1="9" y1="10" x2="15" y2="10"/>
              <line x1="12" y1="7" x2="12" y2="13"/>
            </svg>
          </div>
          <p>暂无会话记录</p>
          <van-button type="primary" round size="small" @click="createNewSession">创建新会话</van-button>
        </div>

        <div v-else class="sessions-list">
          <div
            v-for="session in sessionStore.sessions"
            :key="session.session_id"
            class="session-item"
            :class="{ active: sessionStore.currentSession?.session_id === session.session_id }"
            @click="selectSession(session)"
          >
            <div class="session-info">
              <div class="session-title">{{ session.title || '新会话' }}</div>
              <div class="session-time">{{ formatSessionTime(session.created_at) }}</div>
            </div>
            <span class="delete-btn" @click.stop="deleteSession(session.session_id)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </span>
          </div>
        </div>
      </div>

      <!-- 新会话对话框 -->
      <van-popup v-model:show="showNewSessionDialog" position="bottom">
        <div class="new-session-dialog">
          <h3>新会话</h3>
          <van-field
            v-model="newSessionQuery"
            type="textarea"
            rows="3"
            placeholder="请输入您的问题..."
            maxlength="200"
          />
          <div class="dialog-buttons">
            <van-button @click="showNewSessionDialog = false">取消</van-button>
            <van-button type="primary" @click="confirmNewSession" :disabled="!newSessionQuery.trim()">开始对话</van-button>
          </div>
        </div>
      </van-popup>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { showToast } from 'vant';
import { useSessionStore } from '../store/session';
import { useUserStore } from '../store/user';

const props = defineProps({
  show: { type: Boolean, default: false }
});

const emit = defineEmits(['update:show']);

const router = useRouter();
const sessionStore = useSessionStore();
const userStore = useUserStore();

const showNewSessionDialog = ref(false);
const newSessionQuery = ref('');

// 打开时自动刷新列表
watch(() => props.show, async (val) => {
  if (val) await loadSessions();
});

const loadSessions = async () => {
  if (!userStore.getLoginStatus) {
    showToast('请先登录');
    return;
  }
  if (!userStore.userInfo) {
    const result = await userStore.getUserInfoDetail();
    if (!result.success) return;
  }
  if (userStore.userInfo) {
    const userId = userStore.userInfo.uuid || userStore.userInfo.id || userStore.userInfo.user_id;
    if (userId) await sessionStore.getUserSessions(userId);
  }
};

const formatSessionTime = (timeString) => {
  if (!timeString) return '';
  try {
    const date = new Date(timeString);
    return date.toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
    });
  } catch { return timeString; }
};

const selectSession = (session) => {
  emit('update:show', false);
  router.push(`/aichat/${session.session_id}`);
};

const deleteSession = async (sessionId) => {
  const result = await sessionStore.deleteSession(sessionId);
  showToast(result.success ? '删除成功' : (result.message || '删除失败'));
};

const createNewSession = () => { showNewSessionDialog.value = true; };

const confirmNewSession = async () => {
  if (!newSessionQuery.value.trim()) return;
  const toast = showToast({ type: 'loading', message: '创建中...', forbidClick: true, duration: 0 });
  try {
    const result = await sessionStore.createSession(newSessionQuery.value);
    if (result.success && result.data?.session_id) {
      showNewSessionDialog.value = false;
      newSessionQuery.value = '';
      emit('update:show', false);
      router.push(`/aichat/${result.data.session_id}`);
    } else {
      showToast(result.message || '创建失败');
    }
  } catch (e) {
    showToast('创建失败');
  } finally {
    toast?.close?.();
  }
};
</script>

<style scoped>
.drawer-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg);
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--color-border-light, #ebedf0);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
}

.drawer-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--color-text-light);
}

.empty-sessions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 12px;
  color: var(--color-text-lighter);
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  background: var(--color-card);
  cursor: pointer;
  transition: background 0.15s;
}

.session-item:active {
  background: var(--color-border-light, #f0f0f0);
}

.session-item.active {
  border-left: 3px solid var(--color-primary, #D4914A);
  background: rgba(212, 145, 74, 0.08);
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 15px;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  font-size: 12px;
  color: var(--color-text-lighter);
  margin-top: 4px;
}

.delete-btn {
  flex-shrink: 0;
  padding: 6px;
  margin-left: 8px;
  color: var(--color-text-lighter);
  border-radius: 4px;
  opacity: 0.5;
  transition: opacity 0.2s;
}

.delete-btn:hover { opacity: 1; }
.delete-btn:active { background: var(--color-border-light, #f0f0f0); }

.new-session-dialog {
  background: var(--color-card);
  border-radius: 16px 16px 0 0;
  padding: 20px;
}

.new-session-dialog h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 16px;
  text-align: center;
}

.dialog-buttons {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.dialog-buttons .van-button { flex: 1; }
</style>
