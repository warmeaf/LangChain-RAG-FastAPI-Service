import { defineStore } from 'pinia';

interface LanguageState {
  currentLanguage: string;
}

export const useLanguageStore = defineStore('language', {
  state: (): LanguageState => ({
    currentLanguage: localStorage.getItem('language') || 'zh-CN',
  }),

  getters: {
    getCurrentLanguage: (state: LanguageState): string => state.currentLanguage,
  },

  actions: {
    setLanguage(language: string): void {
      this.currentLanguage = language;
      localStorage.setItem('language', language);
    },
  },
});
