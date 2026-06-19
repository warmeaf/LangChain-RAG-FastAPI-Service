<template>
  <div class="my-page">
    <van-nav-bar :title="$t('my.title')" fixed placeholder />

    <!-- 已登录：用户信息卡片 -->
    <van-cell-group v-if="isLogin" inset class="user-info-group">
      <van-cell center is-link @click="goToProfile">
        <template #icon>
          <van-image
            v-if="userInfo && userInfo.avatar"
            round
            width="72"
            height="72"
            :src="`http://localhost:8001${userInfo.avatar}`"
          >
            <template #error>
              <div class="avatar-letter">
                {{ (userInfo?.username || '?')[0].toUpperCase() }}
              </div>
            </template>
          </van-image>
          <div v-else class="avatar-letter">
            {{ (userInfo?.username || '?')[0].toUpperCase() }}
          </div>
        </template>
        <template #title>
          <span class="cell-username">{{ userInfo?.username || $t('my.notLoggedIn') }}</span>
        </template>
        <template #label>
          <span class="cell-bio">{{ userBio || $t('profile.bio') }}</span>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 未登录：提示卡片 -->
    <van-cell-group v-else inset class="user-info-group">
      <van-cell center>
        <template #icon>
          <div class="avatar-letter">?</div>
        </template>
        <template #title>
          <span class="cell-username">{{ $t('my.notLoggedIn') }}</span>
        </template>
        <template #label>
          <van-button type="primary" size="small" class="login-btn-gap" @click="goToLogin">
            {{ $t('my.goToLogin') }}
          </van-button>
          <van-button size="small" plain @click="goToRegister">
            {{ $t('my.goToRegister') }}
          </van-button>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 菜单列表 -->
    <van-cell-group inset class="menu-list">
      <van-cell :title="$t('my.settings')" is-link @click="goToSettings" />
      <van-cell v-if="isLogin" :title="$t('my.logout')" @click="handleLogout" />
    </van-cell-group>

    <tab-bar />
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useUserStore } from '../store/user';
import { useRouter } from 'vue-router';
import { computed, ref } from 'vue';
import { showDialog, showToast } from 'vant';
import TabBar from '../components/TabBar.vue';
import { useI18n } from 'vue-i18n';

const userStore = useUserStore();
const router = useRouter();
const { t } = useI18n();

// 从store获取用户信息和登录状态
const userInfo = computed(() => userStore.userInfo);
const isLogin = computed(() => userStore.getLoginStatus);
const userBio = computed(() => userStore.getUserBio || t('profile.bio'));

// 跳转到登录页
const goToLogin = () => {
  router.push('/login');
};

// 跳转到注册页
const goToRegister = () => {
  router.push('/register');
};

// 跳转到个人信息页
const goToProfile = () => {
  if (isLogin.value) {
    router.push('/profile');
  }
};



// 跳转到设置页面
const goToSettings = () => {
  router.push('/settings');
};

// 退出登录
const handleLogout = () => {
  showDialog({
    title: t('common.confirm'),
    message: t('my.logout') + '?',
    showCancelButton: true,
  }).then((action) => {
    if (action === 'confirm') {
      userStore.logout();
      router.push('/login');
    }
  });
};

// 获取用户信息
onMounted(async () => {
  try {
    await userStore.getUserInfoDetail();
  } catch (error) {
    console.error('获取用户信息失败:', error);
  }
});
</script>

<style scoped>
/* ======== 页面容器 ======== */
.my-page {
  min-height: 100vh;
  background-color: var(--van-background);
  color: var(--van-text-color);
  padding-bottom: var(--van-tabbar-height);
  box-sizing: border-box;
}

/* ======== 用户信息卡片 ======== */
.user-info-group {
  margin: var(--van-padding-md);
}

.user-info-group :deep(.van-cell) {
  background: linear-gradient(135deg, var(--van-background-2) 0%, var(--van-background) 100%);
  border-radius: calc(var(--van-radius-lg) + var(--van-padding-base));
  padding: var(--van-padding-lg) var(--van-padding-md);
  box-shadow: 0 var(--van-border-width) var(--van-padding-base) rgba(0, 0, 0, 0.08);
}

.user-info-group :deep(.van-cell__icon) {
  margin-right: var(--van-padding-md);
  font-size: 0;
}

/* ======== 头像字母兜底 ======== */
.avatar-letter {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--van-background);
  color: var(--van-primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: var(--van-font-bold);
  border: calc(var(--van-border-width) * 2) solid var(--van-border-color);
}

/* ======== 用户名与简介 ======== */
.cell-username {
  font-size: var(--van-font-size-lg);
  font-weight: var(--van-font-bold);
  color: var(--van-text-color);
}

.cell-bio {
  font-size: var(--van-font-size-md);
  color: var(--van-text-color-3);
}

/* ======== 未登录按钮间距 ======== */
.login-btn-gap {
  margin-right: var(--van-padding-sm);
}

/* ======== 菜单列表 ======== */
.menu-list {
  margin: 0 var(--van-padding-md);
}

.menu-list :deep(.van-cell) {
  border-radius: var(--van-radius-lg);
  margin-bottom: calc(var(--van-padding-base) + var(--van-border-width) * 2);
  background: var(--van-background-2);
  box-shadow: 0 var(--van-border-width) calc(var(--van-border-width) * 2) rgba(0, 0, 0, 0.08);
}
</style>
