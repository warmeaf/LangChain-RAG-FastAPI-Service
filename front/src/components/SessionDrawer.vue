<template>
  <van-popup
    :show="show"
    position="left"
    :style="{ width: '68%', height: '100%' }"
    @update:show="$emit('update:show', $event)"
  >
    <div class="flex flex-col h-full bg-white">
      <!-- 头部 -->
		    <div class="flex items-center justify-between px-4 h-[46px] border-b border-gray-100">
	        <van-button size="small" type="primary" plain @click="createNewSession">新会话</van-button>
      </div>

      <!-- 内容区（可滚动） -->
      <div class="flex-1 overflow-y-auto">
        <!-- 加载中 -->
        <div v-if="sessionStore.isLoading" class="flex flex-col items-center justify-center gap-2 py-16">
          <van-loading type="spinner" />
          <p class="text-sm text-gray-400 m-0">加载中...</p>
        </div>

        <!-- 空状态 -->
        <div v-else-if="sessionStore.sessions.length === 0" class="flex flex-col items-center justify-center gap-4 py-16 px-4">
	          <div class="flex items-center justify-center w-14 h-14 bg-gray-50 rounded-full">
	            <MessageCircle :size="24" color="var(--van-gray-4)" />
	          </div>
          <p class="text-sm text-gray-500 m-0">暂无会话记录</p>
          <van-button type="primary" size="small" @click="createNewSession">创建新会话</van-button>
        </div>

        <!-- 会话列表 -->
        <div v-else class="py-3">
          <van-cell-group inset class="m-0!">
            <van-cell
              v-for="session in sessionStore.sessions"
              :key="session.session_id"
              :title="session.title || '新会话'"
              :label="formatSessionTime(session.created_at || '')"
              center
              @click="selectSession(session)"
            >
              <template #icon>
	                <div class="flex items-center justify-center w-8 h-8 bg-gray-50 rounded-full mr-2">
	                  <MessageCircle :size="14" color="var(--van-gray-5)" />
	                </div>
	              </template>
	              <template #right-icon>
	                <Trash2 :size="18" color="var(--van-gray-4)" class="cursor-pointer" @click.stop="deleteSession(session.session_id || '')" />
              </template>
            </van-cell>
          </van-cell-group>
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { MessageCircle, Trash2 } from '@lucide/vue';
import { showConfirmDialog, showToast } from 'vant';
import { watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSessionStore } from '../store/session';
import { useUserStore } from '../store/user';

const props = defineProps({
  show: { type: Boolean, default: false }
});

const emit = defineEmits(['update:show', 'new-session']);

const router = useRouter();
const route = useRoute();
const sessionStore = useSessionStore();
const userStore = useUserStore();

watch(() => props.show, async (val) => {
  if (val) await loadSessions();
});

const loadSessions = async (): Promise<void> => {
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

const formatSessionTime = (timeString: string) => {
  if (!timeString) return '';
  try {
    const date = new Date(timeString);
    return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch { return timeString; }
};

const selectSession = (session: { session_id: string; title?: string; created_at?: string }) => {
  emit('update:show', false);
  router.push(`/aichat/${session.session_id}`);
};

const deleteSession = async (sessionId: string) => {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: '确定要删除该会话吗？',
    });
  } catch {
    return;
  }
  const currentSessionId = (route.params.sessionId as string | undefined)
    || sessionStore.currentSession?.session_id;
  const isCurrent = currentSessionId === sessionId;
  const result = await sessionStore.deleteSession(sessionId);
  showToast(result.success ? '删除成功' : (result.message || '删除失败'));
  if (isCurrent) {
    emit('new-session');
  }
};

const createNewSession = () => {
  emit('new-session');
  emit('update:show', false);
  router.push('/aichat');
};
</script>

