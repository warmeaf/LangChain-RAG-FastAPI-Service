<template>
  <n-tag :type="tagType" size="small">{{ ext.toUpperCase() }}</n-tag>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'
const props = defineProps<{ filename: string }>()
const ext = computed(() => props.filename.split('.').pop() || '')
const typeMap: Record<string, string> = {
  pdf: 'error', xlsx: 'success', xls: 'success',
  docx: 'info', pptx: 'warning', py: 'default',
  js: 'default', ts: 'default', md: 'info',
}
const tagType = computed(() => typeMap[ext.value] || 'default')
</script>
