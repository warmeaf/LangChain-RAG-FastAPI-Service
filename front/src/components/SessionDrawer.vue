<template>
  <van-popup
    :show="show"
    position="left"
    :style="{ width: '85%', height: '100%' }"
    @update:show="$emit('update:show', $event)"
  >
    <div class="drawer-container">
      <div class="drawer-header">
        <div class="header-title">
          <van-icon name="chat-o" size="20" />
          <span>历史会话</span>
        </div>
        <van-button size="small" type="primary" @click="createNewSession">新会话</van-button>
      </div>

      <div class="drawer-content">
        <div v-if="sessionStore.isLoading" class="loading">
          <van-loading type="spinner" />
          <p>加载中...</p>
        </div>

        <van-empty v-else-if="sessionStore.sessions.length === 0" description="暂无会话记录">
          <van-button type="primary" round size="small" @click="createNewSession">创建新会话</van-button>
        </van-empty>

        <van-cell-group v-else inset>
          <van-swipe-cell v-for="session in sessionStore.sessions" :key="session.session_id">
            <van-cell
              :title="session.title || '新会话'"
              :label="formatSessionTime(session.created_at)"
              :class="{ active: sessionStore.currentSession?.session_id === session.session_id }"
              @click="selectSession(session)"
            />
            <template #right>
              <van-button square type="danger" @click="deleteSession(session.session_id)">
                <van-icon name="delete-o" size="16" />
              </van-button>
            </template>
          </van-swipe-cell>
        </van-cell-group>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { watch } from 'vue';
import { useRouter } from 'vue-router';
import { showToast } from 'vant';
import { useSessionStore } from '../store/session';
import { useUserStore } from '../store/user';

const props = defineProps({
  show: { type: Boolean, default: false }
});

const emit = defineEmits(['update:show', 'new-session']);

const router = useRouter();
const sessionStore = useSessionStore();
const userStore = useUserStore();

watch(() => props.show, async (val) => {
  if (val) await loadSessions();
});

const loadSessions = async () => {
  if (!userStore.getLoginStatus) { showToast('请先登录'); return; }
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
    return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
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

const createNewSession = () => {
  emit('new-session');
  emit('update:show', false);
  router.push('/aichat');
};
</script>

