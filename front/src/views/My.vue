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
          <template #title>
            <div class="flex items-center justify-between w-full">
              <van-image round class="w-12 h-12 object-cover" src="" />
              <div class="flex items-center gap-2">
                <van-button type="primary" size="small" @click="goToLogin">
                  {{ $t('my.goToLogin') }}
                </van-button>
                <van-button size="small" plain @click="goToRegister">
                  {{ $t('my.goToRegister') }}
                </van-button>
              </div>
            </div>
          </template>
        </van-cell>
      </van-cell-group>
    </div>

    <van-cell-group inset>
      <van-cell :title="$t('settings.themeCustomization')" is-link @click="showThemeSheet = true" />
      <van-cell :title="$t('settings.languageSettings')" is-link @click="showLanguageSheet = true" />
    </van-cell-group>

    <van-cell-group inset>
      <van-cell v-if="isLogin" :title="$t('my.logout')" @click="handleLogout" />
    </van-cell-group>
  </div>

  <van-action-sheet
    v-model:show="showThemeSheet"
    :actions="themeActions"
    cancel-text="取消"
    close-on-click-action
    @select="onThemeSelect"
  />

  <van-action-sheet
    v-model:show="showLanguageSheet"
    :actions="languageActions"
    cancel-text="取消"
    close-on-click-action
    @select="onLanguageSelect"
  />

  <tab-bar />
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useUserStore } from '../store/user';
import { useRouter } from 'vue-router';
import { computed } from 'vue';
import { showDialog, showToast } from 'vant';
import TabBar from '../components/TabBar.vue';
import { useI18n } from 'vue-i18n';
import { useThemeStore } from '../store/theme';
import { useLanguageStore } from '../store/language';

const userStore = useUserStore();
const themeStore = useThemeStore();
const languageStore = useLanguageStore();
const router = useRouter();
const { t, locale } = useI18n();

const userInfo = computed(() => userStore.userInfo);
const isLogin = computed(() => userStore.getLoginStatus);
const userBio = computed(() => userStore.getUserBio || t('profile.bio'));

// 主题
const showThemeSheet = ref(false);
const themeActions = [
  { name: '浅色', value: 'light' },
  { name: '深色', value: 'dark' }
];
const onThemeSelect = (action) => {
  themeStore.setTheme(action.value);
};

// 语言
const showLanguageSheet = ref(false);
const languageActions = [
  { name: '简体中文', value: 'zh-CN' },
  { name: 'English', value: 'en-US' }
];
const onLanguageSelect = (action) => {
  languageStore.setLanguage(action.value);
  locale.value = action.value;
  showToast(t('settings.languageChanged'));
  window.location.reload();
};

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
