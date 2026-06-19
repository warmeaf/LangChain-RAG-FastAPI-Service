<template>
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/aichat" name="aichat" icon="chat-o">
      <span>{{ $t('nav.aiChat') }}</span>
    </van-tabbar-item>
    <van-tabbar-item to="/knowledgebase" name="knowledgebase" icon="records-o">
      <span>{{ $t('nav.knowledge') }}</span>
    </van-tabbar-item>
    <van-tabbar-item to="/my" name="my" icon="user-o">
      <span>{{ $t('nav.my') }}</span>
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
