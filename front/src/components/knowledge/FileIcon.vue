<template>
  <component :is="iconComponent" v-bind="$attrs" />
</template>

<script setup lang="ts">
import { FileCode, FileText, Monitor } from '@lucide/vue'
import type { Component } from 'vue'
import { computed } from 'vue'

const props = defineProps<{
  filename: string
}>()

const extMap: Record<string, Component> = {
  pdf: FileText,
  doc: FileText,
  docx: FileText,
  txt: FileText,
  md: FileCode,
  ppt: Monitor,
  pptx: Monitor,
}

const iconComponent = computed<Component>(() => {
  const ext = props.filename?.split('.').pop()?.toLowerCase() || ''
  return extMap[ext] || FileText
})
</script>
