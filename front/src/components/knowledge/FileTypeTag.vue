<template>
  <van-tag :type="tagType" size="medium">{{ ext.toUpperCase() }}</van-tag>
</template>
<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ filename: string }>()
const ext = computed(() => props.filename.split('.').pop() || '')
const typeMap: Record<string, string> = {
  pdf: 'danger', xlsx: 'success', xls: 'success',
  docx: 'primary', pptx: 'warning', py: 'default',
  js: 'default', ts: 'default', md: 'primary',
}
const tagType = computed(() => typeMap[ext.value] || 'default')
</script>
