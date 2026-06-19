<template>
  <div class="analytics-container" style="max-width: 900px; margin: 0 auto; padding: 24px">
    <n-card title="反馈统计">
      <n-grid cols="2" x-gap="12">
        <n-grid-item><n-statistic label="总反馈数" :value="stats.total_feedback" /></n-grid-item>
        <n-grid-item><n-statistic label="好评率" :value="`${(stats.like_rate * 100).toFixed(1)}%`" /></n-grid-item>
      </n-grid>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NGrid, NGridItem, NStatistic } from 'naive-ui'
import { getFeedbackStats } from '../api/feedback'

const stats = ref({ total_feedback: 0, like_rate: 0 })
onMounted(async () => {
  const token = localStorage.getItem('token') || ''
  stats.value = await getFeedbackStats(token)
})
</script>
