<template>
  <div class="settings-container">
    <van-nav-bar
      :title="$t('settings.title')"
      left-arrow
      @click-left="onClickLeft"
    />
    
    <div class="settings-list">
      <van-cell-group inset :title="$t('settings.personalization')">
        <van-cell :title="$t('settings.themeCustomization')" is-link @click="showThemePopup = true" />
        <van-cell :title="$t('settings.languageSettings')" is-link @click="showLanguagePopup = true" />
      </van-cell-group>
    </div>
    
    <!-- 主题选择弹出层 -->
    <van-popup
      v-model:show="showThemePopup"
      position="bottom"
      round
      :style="{ height: '40%' }"
    >
      <div class="popup-title">{{ $t('settings.selectTheme') }}</div>
      <div class="theme-list">
        <div
          class="theme-item"
          :class="{ active: themeStore.currentTheme === 'light' }"
          @click="changeTheme('light')"
        >
          <div class="theme-preview theme-preview-light">
            <div class="theme-preview-bar"></div>
            <div class="theme-preview-card"></div>
          </div>
          <div class="theme-name">浅色</div>
        </div>
        <div
          class="theme-item"
          :class="{ active: themeStore.currentTheme === 'dark' }"
          @click="changeTheme('dark')"
        >
          <div class="theme-preview theme-preview-dark">
            <div class="theme-preview-bar"></div>
            <div class="theme-preview-card"></div>
          </div>
          <div class="theme-name">深色</div>
        </div>
      </div>
    </van-popup>
    
    <!-- 语言选择弹出层 -->
    <van-popup
      v-model:show="showLanguagePopup"
      position="bottom"
      round
      :style="{ height: '40%' }"
    >
      <div class="popup-title">{{ $t('settings.selectLanguage') }}</div>
      <van-radio-group v-model="currentLanguage">
        <van-cell-group inset>
          <van-cell 
            v-for="lang in languageOptions" 
            :key="lang.value" 
            :title="lang.label" 
            clickable 
            @click="currentLanguage = lang.value"
            :class="{ 'language-active': currentLanguage === lang.value }"
          >
            <template #right-icon>
              <van-radio :name="lang.value" />
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
      <div class="popup-footer">
        <van-button type="primary" block @click="changeLanguage">{{ $t('common.confirm') }}</van-button>
      </div>
    </van-popup>
  </div>
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

<style scoped>
.settings-container {
  min-height: 100vh;
  background-color: var(--color-bg);
  color: var(--color-text);
  padding-top: 46px;
  padding-bottom: 20px;
}

.settings-list {
  margin-top: 20px;
}

.popup-title {
  text-align: center;
  padding: 16px;
  font-size: 16px;
  font-weight: 600;
  font-family: var(--font-heading);
  border-bottom: 1px solid var(--color-divider);
  color: var(--color-text);
}

.theme-list {
  display: flex;
  flex-wrap: wrap;
  padding: 20px 16px;
  gap: 12px;
  justify-content: center;
}

.theme-item {
  width: 40%;
  max-width: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  padding: 12px 8px;
  border-radius: 10px;
  transition: background 0.2s;
}

.theme-item:active {
  background: var(--van-background);
}

.theme-item.active {
  background: var(--van-background);
  box-shadow: 0 0 0 2px var(--van-primary-color);
}

.theme-preview {
  width: 72px;
  height: 48px;
  border-radius: 8px;
  margin-bottom: 8px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.theme-preview-light { background: #f7f8fa; }
.theme-preview-dark  { background: #1c1c1e; }

.theme-preview-bar {
  width: 100%;
  height: 6px;
  border-radius: 2px;
  background: var(--van-primary-color);
}

.theme-preview-card {
  width: 70%;
  height: 10px;
  border-radius: 2px;
  background: rgba(127,127,127,0.3);
}

.theme-name {
  font-size: 13px;
  color: var(--color-text-light);
}

.theme-name {
  font-size: 12px;
  color: var(--color-text-light);
}

.popup-footer {
  padding: 16px;
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
}

.language-active {
  background-color: var(--color-surface);
  color: var(--color-text);
}
</style>