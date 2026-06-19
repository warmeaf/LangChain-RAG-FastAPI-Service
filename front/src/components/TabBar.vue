<template>
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/aichat">
      <span>{{ $t('nav.aiChat') }}</span>
      <template #icon>
        <van-icon name="chat-o" size="22" />
      </template>
    </van-tabbar-item>
    <van-tabbar-item to="/knowledgebase">
      <span>{{ $t('nav.knowledge') }}</span>
      <template #icon>
        <van-icon name="records-o" size="22" />
      </template>
    </van-tabbar-item>
    <van-tabbar-item to="/my">
      <span>{{ $t('nav.my') }}</span>
      <template #icon>
        <van-icon name="user-o" size="22" />
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
  if (path.includes('/aichat')) active.value = 0
  else if (path.includes('/knowledgebase')) active.value = 1
  else if (path.includes('/my')) active.value = 2
}

setActiveTab()
watch(() => route.path, () => setActiveTab())
</script>
