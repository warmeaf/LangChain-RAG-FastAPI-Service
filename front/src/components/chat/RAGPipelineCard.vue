<template>
  <div v-if="stages.length > 0" class="pipeline-card">
    <div class="pipeline-title">🔍 RAG 检索过程</div>
    <van-collapse>
      <van-collapse-item v-for="stage in stages" :key="stage.stage" :title="stage.title">
        <p>{{ stage.content }}</p>
        <div v-if="stage.details?.documents" class="doc-tags">
          <van-tag v-for="d in stage.details.documents" :key="d.index" size="medium">
            #{{ d.index }} {{ d.preview?.slice(0, 60) }}
          </van-tag>
        </div>
      </van-collapse-item>
    </van-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const stages = ref<any[]>([])
const stageMap: Record<string, string> = {
  query_processing: '① 查询预处理', hyde: '② HyDE 假设文档',
  retrieval: '③ 粗排检索', reorder: '④ 精排重排',
  ranking: '⑤ 多因素排序', summarize: '⑥ 分批总结',
}

function addStage(data: any) {
  stages.value = [...stages.value.filter(s => s.stage !== data.stage), {
    stage: data.stage, title: stageMap[data.stage] || data.stage,
    content: data.content, details: data.details,
  }]
}
function reset() { stages.value = [] }
defineExpose({ addStage, reset })
</script>

