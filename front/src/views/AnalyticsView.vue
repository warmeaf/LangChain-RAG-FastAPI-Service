<template>
  <div class="analytics-container">
    <div class="analytics-card">
      <h3>反馈统计</h3>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-label">总反馈数</span>
          <span class="stat-value">{{ stats.total_feedback }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">好评率</span>
          <span class="stat-value">{{ (stats.like_rate * 100).toFixed(1) }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getFeedbackStats } from '../api/feedback'

const stats = ref({ total_feedback: 0, like_rate: 0 })
onMounted(async () => {
  const token = localStorage.getItem('token') || ''
  stats.value = await getFeedbackStats(token)
})
</script>

<style scoped>
.analytics-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}
.analytics-card {
  background: var(--color-card);
  border-radius: 8px;
  padding: 16px;
}
.analytics-card h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
  color: var(--color-text);
}
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.stat-item {
  text-align: center;
  padding: 12px;
  background: var(--color-bg);
  border-radius: 6px;
}
.stat-label { font-size: 13px; color: var(--color-text-lighter); display: block; }
.stat-value { font-size: 24px; font-weight: 700; color: var(--color-primary); margin-top: 4px; }
</style>
