<template>
  <van-nav-bar
    title="个人信息"
    left-arrow
    @click-left="$router.back()"
    fixed
    placeholder
  />

  <div class="flex flex-col gap-4 mt-4">
    <van-cell-group inset>
	      <van-cell title="头像" center is-link @click="editAvatar">
        <template #right-icon>
          <van-image v-if="userInfo?.avatar" round class="w-12 object-cover" :src="`http://localhost:8001${userInfo.avatar}`" />
          <div v-else class="flex w-12 h-12 items-center justify-center">
            {{ (userInfo?.username || '?')[0].toUpperCase() }}
          </div>
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group inset>
      <van-cell title="用户ID" :value="userInfo?.id || userInfo?.uuid || '未设置'" />
      <van-cell title="用户名" :value="userInfo?.username || '未设置'" is-link @click="editUsername" />
      <van-cell title="邮箱" :value="userInfo?.email || '未设置'" is-link @click="editEmail" />
      <van-cell title="手机号" :value="userInfo?.telephone || '未设置'" is-link @click="editPhone" />
      <van-cell title="性别" :value="genderText || '未设置'" is-link @click="editGender" />
      <van-cell title="个人简介" :value="userBio || '暂无简介'" is-link @click="editBio" />
      <van-cell title="注册时间" :value="createTimeText || '未设置'" />
      <van-cell title="最后登录时间" :value="lastLoginText || '未设置'" />
    </van-cell-group>

    <van-cell-group inset>
      <van-cell title="修改密码" is-link @click="changePassword" />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { showFailToast, showLoadingToast, showToast } from 'vant';
import { computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProfileEdit } from '../composables/useProfileEdit';
import { useUserStore } from '../store/user';

const router = useRouter();
const userStore = useUserStore();
const { editUsername, editEmail, editPhone, editBio, editGender, editAvatar, changePassword } = useProfileEdit();

// 初始化用户状态
onMounted(async () => {
  if (!userStore.getLoginStatus) {
    router.push('/login');
    return;
  }

  try {
    const loadingInstance = showLoadingToast({ message: '加载中...', forbidClick: true, duration: 0 });
    const result = await userStore.getUserInfoDetail();
    loadingInstance.close();
    if (!result.success) showFailToast(result.message || '获取用户信息失败');
  } catch {
    (showToast as unknown as { clear: () => void }).clear();
    (showToast as unknown as { fail: (m: string) => void }).fail('获取用户信息失败');
  }
});

const userInfo = computed(() => userStore.userInfo);
const userBio = computed(() => userStore.userInfo?.bio || '暂无简介');

const genderText = computed(() => {
  switch (userInfo.value?.gender) {
    case 1: return '男';
    case 2: return '女';
    default: return '其他';
  }
});

const createTimeText = computed(() => {
  if (!userInfo.value?.create_time) return '未设置';
  return new Date(userInfo.value.create_time).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  });
});

const lastLoginText = computed(() => {
  if (!userInfo.value?.last_login) return '未设置';
  return new Date(userInfo.value.last_login).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  });
});
</script>