<template>
  <n-card v-if="stages.length > 0" size="small" title="🔍 RAG 检索过程" class="pipeline-card">
    <n-collapse>
      <n-collapse-item v-for="stage in stages" :key="stage.stage" :title="stage.title">
        <p>{{ stage.content }}</p>
        <div v-if="stage.details?.documents">
          <n-tag v-for="d in stage.details.documents" :key="d.index" size="small" style="margin: 2px">
            #{{ d.index }} {{ d.preview?.slice(0, 60) }}
          </n-tag>
        </div>
      </n-collapse-item>
    </n-collapse>
  </n-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NCard, NCollapse, NCollapseItem, NTag } from 'naive-ui'

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
