<template>
  <van-config-provider :theme="themeStore.currentTheme === 'dark' ? 'dark' : undefined">
    <div>
      <router-view v-slot="{ Component }">
        <template v-if="$route.meta.keepAlive">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </template>
        <template v-else>
          <component :is="Component" />
        </template>
      </router-view>
    </div>
  </van-config-provider>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useThemeStore } from './store/theme'
import { useUserStore } from './store/user'

const themeStore = useThemeStore()
const userStore = useUserStore()
onMounted(() => {
  themeStore.initTheme()
  // 刷新后从 localStorage 恢复 pinia 登录态，使 UI 与路由守卫的真相源一致
  userStore.restoreSession()
})
</script>
