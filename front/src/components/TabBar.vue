<template>
  <van-tabbar v-model="active" placeholder>
    <van-tabbar-item name="aichat" @click="router.push('/aichat')">
      <template #icon>
        <MessageCircle />
      </template>
      <span>{{ $t('nav.aiChat') }}</span>
    </van-tabbar-item>
    <van-tabbar-item name="knowledgebase" @click="router.push('/knowledgebase')">
      <template #icon>
        <Database />
      </template>
      <span>{{ $t('nav.knowledge') }}</span>
    </van-tabbar-item>
    <van-tabbar-item name="my" @click="router.push('/my')">
      <template #icon>
        <User />
      </template>
      <span>{{ $t('nav.my') }}</span>
    </van-tabbar-item>
  </van-tabbar>
</template>

<script setup lang="ts">
import { Database, MessageCircle, User } from '@lucide/vue'
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
