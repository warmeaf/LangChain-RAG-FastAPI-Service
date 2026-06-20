<template>
  <van-nav-bar
    :title="$t('settings.title')"
    left-arrow
    @click-left="onClickLeft"
  />

  <van-cell-group inset :title="$t('settings.personalization')">
    <van-cell :title="$t('settings.themeCustomization')" is-link @click="showThemeSheet = true" />
    <van-cell :title="$t('settings.languageSettings')" is-link @click="showLanguageSheet = true" />
  </van-cell-group>

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
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { showToast } from 'vant';
import { useThemeStore } from '../store/theme';
import { useI18n } from 'vue-i18n';
import { useLanguageStore } from '../store/language';

const router = useRouter();
const themeStore = useThemeStore();
const languageStore = useLanguageStore();
const { t, locale } = useI18n();

// 返回上一页
const onClickLeft = () => {
  router.back();
};

	// 主题相关
const showThemeSheet = ref(false);
const themeActions = [
  { name: '浅色', value: 'light' },
  { name: '深色', value: 'dark' }
];

const onThemeSelect = (action) => {
  themeStore.setTheme(action.value);
};

	// 语言相关
const showLanguageSheet = ref(false);
const languageActions = [
  { name: '简体中文', value: 'zh-CN' },
  { name: 'English', value: 'en-US' }
];

// 选择语言
const onLanguageSelect = (action) => {
  languageStore.setLanguage(action.value);
  locale.value = action.value;
  showToast(t('settings.languageChanged'));
  window.location.reload();
};
</script>
