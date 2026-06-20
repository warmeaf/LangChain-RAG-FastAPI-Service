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

const themeStore = useThemeStore()
onMounted(() => themeStore.initTheme())
</script>
