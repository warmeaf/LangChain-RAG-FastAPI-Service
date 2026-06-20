import { createI18n, type I18n } from 'vue-i18n';
import enUS from './locales/en-US';
import zhCN from './locales/zh-CN';
import type { LocaleMessages } from './types';

export function setupI18n(): I18n {
  const savedLanguage = localStorage.getItem('language') || 'zh-CN';

  const i18n = createI18n({
    legacy: false,
    locale: savedLanguage,
    fallbackLocale: 'zh-CN',
    messages: {
      'zh-CN': zhCN as unknown as Parameters<typeof createI18n>[0] extends { messages?: infer M }
        ? M[keyof M]
        : never,
      'en-US': enUS as unknown as Parameters<typeof createI18n>[0] extends { messages?: infer M }
        ? M[keyof M]
        : never,
    },
  });

  return i18n as unknown as I18n;
}

export function setI18nLanguage(i18n: I18n, locale: string): void {
  if (i18n.mode === 'legacy') {
    i18n.global.locale = locale;
  } else {
    (i18n.global.locale as { value: string }).value = locale;
  }
  document.querySelector('html')?.setAttribute('lang', locale);
}

export type { LocaleMessages };
