import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/aichat' },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', keepAlive: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { title: '注册', keepAlive: false },
  },
  {
    path: '/aichat',
    name: 'AIChat',
    component: () => import('../views/AIChat.vue'),
    meta: { title: 'AI问答', keepAlive: true },
  },
  {
    path: '/aichat/:sessionId',
    name: 'AIChatWithSession',
    component: () => import('../views/AIChat.vue'),
    meta: { title: 'AI问答', keepAlive: true },
  },
  {
    path: '/my',
    name: 'My',
    component: () => import('../views/My.vue'),
    meta: { title: '我的', keepAlive: true },
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/Profile.vue'),
    meta: { title: '个人信息', keepAlive: false },
  },
  {
    path: '/knowledgebase',
    name: 'KnowledgeBase',
    component: () => import('../views/KnowledgeBase.vue'),
    meta: { title: '知识库管理', keepAlive: false },
  },
  { path: '/sessions', redirect: '/aichat' },
  { path: '/settings', redirect: '/my' },
  {
    path: '/analytics',
    name: 'Analytics',
    component: () => import('../views/AnalyticsView.vue'),
    meta: { title: '数据分析', keepAlive: false },
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.beforeEach((to, _from) => {
  document.title = (to.meta.title as string) || '新闻资讯';
});

export default router;
