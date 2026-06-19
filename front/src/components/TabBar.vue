<template>
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/aichat">
      <span>{{ $t('nav.aiChat') }}</span>
      <template #icon="props">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          <line x1="9" y1="10" x2="15" y2="10"/>
          <line x1="12" y1="7" x2="12" y2="13"/>
        </svg>
      </template>
    </van-tabbar-item>
    <van-tabbar-item to="/my">
      <span>{{ $t('nav.my') }}</span>
      <template #icon="props">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
          <circle cx="12" cy="7" r="4"/>
        </svg>
      </template>
    </van-tabbar-item>
  </van-tabbar>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const active = ref(0)

const setActiveTab = () => {
  const path = route.path
  if (path.includes('/aichat')) {
    active.value = 0
  } else if (path.includes('/my')) {
    active.value = 1
  }
}

setActiveTab()

watch(() => route.path, () => {
  setActiveTab()
})
</script>
