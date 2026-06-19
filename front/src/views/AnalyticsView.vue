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
  margin: 0 auto;
  padding: var(--van-padding-lg);
}
.analytics-card {
  background: var(--van-background-2);
  border-radius: var(--van-radius-lg);
  padding: var(--van-padding-md);
}
.analytics-card h3 {
  font-size: var(--van-font-size-lg);
  font-weight: var(--van-font-bold);
  margin: 0 0 var(--van-padding-md);
  color: var(--van-text-color);
}
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--van-padding-sm);
}
.stat-item {
  text-align: center;
  padding: var(--van-padding-sm);
  background: var(--van-background);
}
.stat-label { font-size: var(--van-font-size-md); color: var(--van-text-color-3); display: block; }
.stat-value { font-weight: var(--van-font-bold); color: var(--van-primary-color); margin-top: var(--van-padding-base); }
</style>
