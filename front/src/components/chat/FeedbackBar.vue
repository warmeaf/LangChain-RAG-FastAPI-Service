<template>
  <div class="feedback-bar">
    <span
      class="feedback-btn"
      :class="{ active: value === 'like' }"
      @click="$emit('feedback', 'like')"
    >
      <van-icon name="good-job" />
    </span>
    <span
      class="feedback-btn"
      :class="{ active: value === 'dislike' }"
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

<style scoped>
.feedback-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.feedback-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--color-border, #ddd);
  cursor: pointer;
  color: var(--color-text-lighter);
  transition: all 0.2s;
}
.feedback-btn.active {
  color: #fff;
  border-color: transparent;
}
.feedback-btn:first-child.active { background: var(--van-green, #07c160); }
.feedback-btn:last-child.active { background: var(--van-red, #ee0a24); }
</style>
