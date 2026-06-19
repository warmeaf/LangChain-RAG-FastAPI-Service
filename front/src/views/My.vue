<template>
  <div class="my-container">
    <van-nav-bar :title="$t('my.title')" />
    <div class="user-info" @click="goToProfile" v-if="isLogin">
      <div class="avatar">
        <div v-if="userInfo && userInfo.avatar" class="avatar-img">
          <van-image round width="72" height="72" :src="`http://localhost:8001${userInfo.avatar}`" />
        </div>
        <div v-else class="avatar-letter">
          {{ (userInfo?.username || '?')[0].toUpperCase() }}
        </div>
      </div>
      <div class="info">
        <div class="username">{{ userInfo?.username || $t('my.notLoggedIn') }}</div>
        <div class="desc">{{ userBio || $t('profile.bio') }}</div>
      </div>
      <van-icon name="arrow" class="arrow-icon" />
    </div>
    <div class="user-info" v-else>
      <div class="avatar">
        <div class="avatar-letter">?</div>
      </div>
      <div class="info">
        <div class="username">{{ $t('my.notLoggedIn') }}</div>
        <div class="desc">
          <van-button type="primary" size="small" @click="goToLogin" style="margin-right: 10px">{{ $t('my.goToLogin') }}</van-button>
          <van-button size="small" plain @click="goToRegister">{{ $t('my.goToRegister') }}</van-button>
        </div>
      </div>
    </div>

    <div class="menu-list">
      <van-cell-group inset>
        <van-cell :title="$t('my.settings')" is-link @click="goToSettings" />
        <van-cell v-if="isLogin" :title="$t('my.logout')" @click="handleLogout" />
      </van-cell-group>
    </div>
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
.my-container {
  padding-top: 46px;
  padding-bottom: 50px;
  background-color: var(--van-background);
  color: var(--van-text-color);
  min-height: 100vh;
  box-sizing: border-box;
}

.van-nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  z-index: 999;
}

.user-info {
  display: flex;
  align-items: center;
  padding: var(--van-padding-lg) 16px;
  background: linear-gradient(135deg, var(--van-background-2) 0%, var(--van-background) 100%);
  color: var(--van-text-color);
  border-radius: 12px;
  margin: var(--van-padding-md);
  position: relative;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.arrow-icon {
  position: absolute;
  right: 16px;
  color: var(--van-text-color-3);
}

.avatar {
  margin-right: 16px;
  flex-shrink: 0;
}

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
  border: 2px solid var(--van-border-color);
}

.info {
  flex: 1;
}

.username {
  font-size: 18px;
  font-weight: var(--van-font-bold);
  
  margin-bottom: var(--van-padding-base);
  color: var(--van-text-color);
}

.desc {
  font-size: var(--van-font-size-md);
  color: var(--van-text-color-3);
}

.menu-list {
  margin: 0 var(--van-padding-md);
}

.menu-list :deep(.van-cell) {
  border-radius: 8px;
  margin-bottom: 6px;
  background: var(--van-background-2);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
</style>