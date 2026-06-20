<template>
  <van-nav-bar :title="$t('my.title')" fixed placeholder />

  <div class="flex flex-col gap-6 mt-4">
    <div>
      <van-cell-group v-if="isLogin" inset>
        <van-cell center is-link @click="goToProfile">
          <template #icon>
            <van-image round class="w-12 h-12 object-cover mr-2"
              :src="userInfo?.avatar ? `http://localhost:8001${userInfo.avatar}` : ''" />
          </template>
          <template #title>
            <span>{{ userInfo?.username || $t('my.notLoggedIn') }}</span>
          </template>
          <template #label>
            <span>{{ userBio || $t('profile.bio') }}</span>
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group v-else inset>
        <van-cell center>
          <template #icon>
            <van-image round width="72" height="72" src="" />
          </template>
          <template #title>
            <span>{{ $t('my.notLoggedIn') }}</span>
          </template>
          <template #label>
            <van-space>
              <van-button type="primary" size="small" @click="goToLogin">
                {{ $t('my.goToLogin') }}
              </van-button>
              <van-button size="small" plain @click="goToRegister">
                {{ $t('my.goToRegister') }}
              </van-button>
            </van-space>
          </template>
        </van-cell>
      </van-cell-group>
    </div>


    <van-cell-group inset>
      <van-cell :title="$t('my.settings')" is-link @click="goToSettings" />
      <van-cell v-if="isLogin" :title="$t('my.logout')" @click="handleLogout" />
    </van-cell-group>
  </div>

  <tab-bar />
</template>

<script setup>
import { onMounted } from 'vue';
import { useUserStore } from '../store/user';
import { useRouter } from 'vue-router';
import { computed } from 'vue';
import { showDialog } from 'vant';
import TabBar from '../components/TabBar.vue';
import { useI18n } from 'vue-i18n';

const userStore = useUserStore();
const router = useRouter();
const { t } = useI18n();

const userInfo = computed(() => userStore.userInfo);
const isLogin = computed(() => userStore.getLoginStatus);
const userBio = computed(() => userStore.getUserBio || t('profile.bio'));

const goToLogin = () => {
  router.push('/login');
};

const goToRegister = () => {
  router.push('/register');
};

const goToProfile = () => {
  if (isLogin.value) {
    router.push('/profile');
  }
};

const goToSettings = () => {
  router.push('/settings');
};

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

onMounted(async () => {
  try {
    await userStore.getUserInfoDetail();
  } catch (error) {
    console.error('获取用户信息失败:', error);
  }
});
</script>
