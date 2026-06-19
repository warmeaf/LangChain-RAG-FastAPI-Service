<template>
  <van-slider :model-value="weight" :min="0.1" :max="1.0" :step="0.05" @update:model-value="$emit('update:weight', $event)" />
</template>
<script setup lang="ts">
defineProps<{ weight: number }>()
defineEmits<{ 'update:weight': [value: number] }>()
</script>
