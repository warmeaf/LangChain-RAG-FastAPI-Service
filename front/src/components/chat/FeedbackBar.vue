<template>
  <n-space align="center" size="small">
    <n-button size="tiny" circle @click="$emit('feedback', 'like')" :type="value === 'like' ? 'success' : 'default'">
      <template #icon><n-icon><ThumbsUpOutline /></n-icon></template>
    </n-button>
    <n-button size="tiny" circle @click="$emit('feedback', 'dislike')" :type="value === 'dislike' ? 'error' : 'default'">
      <template #icon><n-icon><ThumbsDownOutline /></n-icon></template>
    </n-button>
    <n-rate v-if="showRating" :value="rating" @update:value="$emit('rate', $event)" size="small" />
  </n-space>
</template>

<script setup lang="ts">
import { NSpace, NButton, NRate, NIcon } from 'naive-ui'
import { ThumbsUpOutline, ThumbsDownOutline } from '@vicons/ionicons5'
defineProps<{ value?: string; rating?: number; showRating?: boolean }>()
defineEmits<{ feedback: [type: string]; rate: [value: number] }>()
</script>
