<template>
  <!-- PDF -->
  <svg v-if="type === 'pdf'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" v-bind="$attrs">
    <path d="M6 2h8l4 4v14a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" stroke-width="1.5" />
    <path d="M14 2v4h4" stroke="currentColor" stroke-width="1.5" />
    <!-- PDF 标签底框 -->
    <rect x="7" y="10" width="10" height="7" rx="1.5" fill="currentColor" opacity="0.12" />
    <!-- P 字母 -->
    <path d="M9.5 11.5v4M9.5 11.5h2.2a1.8 1.8 0 010 3.6H9.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" />
  </svg>

  <!-- DOCX -->
  <svg v-else-if="type === 'docx'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" v-bind="$attrs">
    <path d="M6 2h8l4 4v14a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" stroke-width="1.5" />
    <path d="M14 2v4h4" stroke="currentColor" stroke-width="1.5" />
    <rect x="7" y="10" width="10" height="7" rx="1.5" fill="currentColor" opacity="0.1" />
    <!-- W 字母 -->
    <path d="M8.5 13l1.5 3 1.5-3 1.5 3 1.5-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
  </svg>

  <!-- PPTX -->
  <svg v-else-if="type === 'pptx'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" v-bind="$attrs">
    <!-- 投影屏幕 -->
    <rect x="3" y="3" width="18" height="13" rx="1.5" stroke="currentColor" stroke-width="1.5" />
    <path d="M12 16v4" stroke="currentColor" stroke-width="1.5" />
    <path d="M8 20h8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <!-- 屏幕内的柱状图 -->
    <rect x="6" y="10" width="3" height="4" rx="0.5" fill="currentColor" opacity="0.3" />
    <rect x="10.5" y="7" width="3" height="7" rx="0.5" fill="currentColor" opacity="0.3" />
    <rect x="15" y="8.5" width="3" height="5.5" rx="0.5" fill="currentColor" opacity="0.3" />
  </svg>

  <!-- Markdown -->
  <svg v-else-if="type === 'md'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" v-bind="$attrs">
    <path d="M6 2h8l4 4v14a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" stroke-width="1.5" />
    <path d="M14 2v4h4" stroke="currentColor" stroke-width="1.5" />
    <!-- # 符号 -->
    <path d="M9 10h6M9 17h6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
    <path d="M10.5 8l-1 11" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
    <path d="M13.5 8l-1 11" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
  </svg>

  <!-- TXT -->
  <svg v-else viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" v-bind="$attrs">
    <path d="M6 2h8l4 4v14a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" stroke-width="1.5" />
    <path d="M14 2v4h4" stroke="currentColor" stroke-width="1.5" />
    <!-- 文本横线 -->
    <line x1="8" y1="11" x2="16" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="8" y1="14" x2="16" y2="14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="8" y1="17" x2="13" y2="17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  filename: string
}>()

const type = computed(() => {
  const ext = props.filename?.split('.').pop()?.toLowerCase() || ''
  if (['pdf'].includes(ext)) return 'pdf'
  if (['doc', 'docx'].includes(ext)) return 'docx'
  if (['ppt', 'pptx'].includes(ext)) return 'pptx'
  if (['md', 'markdown'].includes(ext)) return 'md'
  return 'txt'
})
</script>
