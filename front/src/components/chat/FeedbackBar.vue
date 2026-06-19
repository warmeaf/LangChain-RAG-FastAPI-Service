<template>
  <div>
    <span
     
     
      @click="$emit('feedback', 'like')"
    >
      <van-icon name="good-job" />
    </span>
    <span
     
     
      @click="$emit('feedback', 'dislike')"
    >
      <van-icon name="good-job-o" />
    </span>
    <van-rate
      v-if="showRating"
      :model-value="rating"
      size="16"
      @update:model-value="$emit('rate', $event)"
    />
  </div>
</template>

<script setup>
defineProps<{ value?: string; rating?: number; showRating?: boolean }>()
defineEmits<{ feedback: [type: string]; rate: [value: number] }>()
</script>

