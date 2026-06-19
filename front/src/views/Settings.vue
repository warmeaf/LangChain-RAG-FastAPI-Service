<template>
  <van-nav-bar
    :title="$t('settings.title')"
    left-arrow
    @click-left="onClickLeft"
  />

  <van-cell-group inset :title="$t('settings.personalization')">
    <van-cell :title="$t('settings.themeCustomization')" is-link @click="showThemePopup = true" />
    <van-cell :title="$t('settings.languageSettings')" is-link @click="showLanguagePopup = true" />
  </van-cell-group>

  <van-popup
    v-model:show="showThemePopup"
    position="bottom"
    round
  >
    <div>{{ $t('settings.selectTheme') }}</div>
    <div>
      <div @click="changeTheme('light')">
        <div>
          <div></div>
          <div></div>
        </div>
        <div>浅色</div>
      </div>
      <div @click="changeTheme('dark')">
        <div>
          <div></div>
          <div></div>
        </div>
        <div>深色</div>
      </div>
    </div>
  </van-popup>

  <van-popup
    v-model:show="showLanguagePopup"
    position="bottom"
    round
  >
    <div>{{ $t('settings.selectLanguage') }}</div>
    <van-radio-group v-model="currentLanguage">
      <van-cell-group inset>
        <van-cell
          v-for="lang in languageOptions"
          :key="lang.value"
          :title="lang.label"
          clickable
          @click="currentLanguage = lang.value"
        >
          <template #right-icon>
            <van-radio :name="lang.value" />
          </template>
        </van-cell>
      </van-cell-group>
    </van-radio-group>
    <div>
      <van-button type="primary" block @click="changeLanguage">{{ $t('common.confirm') }}</van-button>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, computed } from 'vue';
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
const showThemePopup = ref(false);

// 切换主题
const changeTheme = (themeId) => {
  themeStore.setTheme(themeId);
  showThemePopup.value = false;
};

// 语言相关
const showLanguagePopup = ref(false);
const currentLanguage = ref(languageStore.getCurrentLanguage);
const languageOptions = [
  { label: '简体中文', value: 'zh-CN' },
  { label: 'English', value: 'en-US' }
];

// 切换语言
const changeLanguage = () => {
  languageStore.setLanguage(currentLanguage.value);
  locale.value = currentLanguage.value;
  showLanguagePopup.value = false;
  showToast(t('settings.languageChanged'));
  // 强制刷新页面以应用语言更改
  window.location.reload();
};
</script>
