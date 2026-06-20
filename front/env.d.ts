/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue';

  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>;
  export default component;
}

declare module '*.css' {
  const content: string;
  export default content;
}

interface ImportMetaEnv {
  readonly VITE_BASE_URL: string;
  readonly VITE_API_BASE_URL: string;
  readonly VITE_USER_BASE_URL: string;
  readonly BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Vant 4.x types resolution for moduleResolution: "bundler"
declare module 'vant' {
  export * from 'vant/lib/index';
}
