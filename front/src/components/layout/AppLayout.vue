<template>
  <n-config-provider :locale="zhCN">
    <n-layout style="min-height: 100vh">
      <n-layout-header bordered>
        <div class="header-content">
          <n-space align="center">
            <h2 class="app-title">企业知识库</h2>
          </n-space>
          <n-space>
            <n-button @click="$router.push('/aichat')" :type="$route.path.startsWith('/aichat') ? 'primary' : 'default'">对话</n-button>
            <n-button @click="$router.push('/knowledgebase')" :type="$route.path === '/knowledgebase' ? 'primary' : 'default'">知识库</n-button>
            <n-button @click="$router.push('/analytics')" :type="$route.path === '/analytics' ? 'primary' : 'default'">分析</n-button>
          </n-space>
        </div>
      </n-layout-header>
      <n-layout-content>
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-config-provider>
</template>

<script setup lang="ts">
import { NConfigProvider, NLayout, NLayoutHeader, NLayoutContent, NSpace, NButton } from 'naive-ui'
import { zhCN } from 'naive-ui'
</script>

<style scoped>
.header-content { display: flex; justify-content: space-between; align-items: center; padding: 0 24px; height: 64px; }
.app-title { margin: 0; font-size: 20px; }
</style>
