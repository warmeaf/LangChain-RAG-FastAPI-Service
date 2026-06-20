import { defineStore } from 'pinia';

interface ThemeState {
  currentTheme: string;
}

export const useThemeStore = defineStore('theme', {
  state: (): ThemeState => ({
    currentTheme: localStorage.getItem('theme') || 'light',
  }),

  getters: {
    getCurrentTheme: (state: ThemeState): string => state.currentTheme,
    isDark: (state: ThemeState): boolean => state.currentTheme === 'dark',
  },

  actions: {
    setTheme(themeName: string): void {
      this.currentTheme = themeName;
      localStorage.setItem('theme', themeName);
    },

    toggleTheme(): void {
      this.setTheme(this.currentTheme === 'dark' ? 'light' : 'dark');
    },

    applyTheme(): void {
      // Vant van-config-provider auto-handles dark mode via :theme prop
    },

    initTheme(): void {
      this.applyTheme();
    },
  },
});
