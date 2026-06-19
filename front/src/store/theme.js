import { defineStore } from 'pinia';

export const useThemeStore = defineStore('theme', {
  state: () => ({
    currentTheme: localStorage.getItem('theme') || 'light',
  }),

  getters: {
    getCurrentTheme: (state) => state.currentTheme,
    isDark: (state) => state.currentTheme === 'dark',
  },

  actions: {
    setTheme(themeName) {
      this.currentTheme = themeName;
      localStorage.setItem('theme', themeName);
    },

    toggleTheme() {
      this.setTheme(this.currentTheme === 'dark' ? 'light' : 'dark');
    },

    applyTheme() {
      // Vant van-config-provider 通过 :theme 属性自动处理深色模式
      // 无需手动设置 CSS 变量
    },

    initTheme() {
      this.applyTheme();
    },
  },
});
