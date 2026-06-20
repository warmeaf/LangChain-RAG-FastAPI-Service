<template>
  <div>
    <div>
      <h3>反馈统计</h3>
      <div>
        <div>
          <span>总反馈数</span>
          <span>{{ stats.total_feedback }}</span>
        </div>
        <div>
          <span>好评率</span>
          <span>{{ (stats.like_rate * 100).toFixed(1) }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getFeedbackStats } from '../api/feedback'

const stats = ref({ total_feedback: 0, like_rate: 0 })
onMounted(async () => {
  const token = localStorage.getItem('token') || ''
  stats.value = await getFeedbackStats(token)
})
</script>

