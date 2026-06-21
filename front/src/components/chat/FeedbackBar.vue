<template>
  <div class="flex items-center gap-3">
    <span class="cursor-pointer" @click="$emit('feedback', 'like')">
      <ThumbsUp :size="16" />
    </span>
    <span class="cursor-pointer" @click="$emit('feedback', 'dislike')">
      <ThumbsDown :size="16" />
    </span>
    <van-rate v-if="showRating" :model-value="rating" size="16" @update:model-value="$emit('rate', $event)" />
  </div>
</template>

<script setup lang="ts">
import { ThumbsDown, ThumbsUp } from '@lucide/vue'

defineProps<{ value?: string, rating?: number, showRating?: boolean }>()
defineEmits<{ feedback: [string], rate: [number] }>()
</script>
