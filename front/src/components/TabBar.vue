<template>
  <van-tabbar v-model="active" placeholder>
    <van-tabbar-item name="aichat" icon="chat-o" @click="router.push('/aichat')">
      <span>{{ $t('nav.aiChat') }}</span>
    </van-tabbar-item>
    <van-tabbar-item name="knowledgebase" icon="records-o" @click="router.push('/knowledgebase')">
      <span>{{ $t('nav.knowledge') }}</span>
    </van-tabbar-item>
    <van-tabbar-item name="my" icon="user-o" @click="router.push('/my')">
      <span>{{ $t('nav.my') }}</span>
    </van-tabbar-item>
  </van-tabbar>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const active = ref('aichat')

const setActiveTab = () => {
  const path = route.path
  if (path.startsWith('/aichat')) active.value = 'aichat'
  else if (path.startsWith('/knowledgebase')) active.value = 'knowledgebase'
  else if (path.startsWith('/my')) active.value = 'my'
}

setActiveTab()
watch(() => route.path, () => setActiveTab())
</script>
