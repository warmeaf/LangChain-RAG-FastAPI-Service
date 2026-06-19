<template>
  <n-slider :value="weight" :min="0.1" :max="1.0" :step="0.05" @update:value="$emit('update:weight', $event)" />
</template>
<script setup lang="ts">
import { NSlider } from 'naive-ui'
defineProps<{ weight: number }>()
defineEmits<{ 'update:weight': [value: number] }>()
</script>
