<template>
  <div v-if="thinking && thinking.length > 0" class="mb-2">
    <div class="flex items-center justify-between py-1.5 px-2 bg-gray-100 rounded cursor-pointer select-none mb-2"
      @click="$emit('toggle')">
      <span class="text-xs font-medium text-gray-600">💬 思考过程</span>
      <span class="text-xs text-gray-400">{{ collapsed ? '展开' : '收起' }}</span>
    </div>
    <div v-show="!collapsed" class="flex flex-col gap-2">
      <div v-for="(step, sIndex) in thinking" :key="sIndex"
        class="border border-gray-100 rounded-lg p-2.5">
        <div class="flex items-center gap-2 mb-1">
          <van-tag :color="getStageColor(step.stage)" size="medium" text-color="var(--van-white)">
            {{ getStageLabel(step.stage) }}
          </van-tag>
          <span class="text-xs text-gray-700">{{ step.content }}</span>
        </div>
        <div v-if="step.details" class="mt-2 pl-1">
          <template v-if="step.details.documents">
            <div v-for="(doc, dIndex) in step.details.documents.slice(0, 3)" :key="dIndex"
              class="flex items-center justify-between text-xs py-0.5">
              <span class="text-gray-600 truncate mr-2">{{ doc.source }}</span>
              <span v-if="doc.score !== undefined && doc.score !== null" class="text-gray-400 shrink-0">
                {{ (doc.score * 100).toFixed(0) }}%
              </span>
            </div>
            <div v-if="step.details.documents.length > 3" class="text-xs text-gray-400 mt-1">
              ... 还有 {{ step.details.documents.length - 3 }} 个文档
            </div>
          </template>
          <template v-else-if="step.details.scores">
            <div v-for="(sc, cIndex) in step.details.scores.slice(0, 3)" :key="cIndex"
              class="flex items-center gap-2 text-xs py-0.5">
              <span class="text-gray-400">#{{ sc.rank || sc.index }}</span>
              <span class="text-gray-600">{{ (sc.score * 100).toFixed(0) }}%</span>
              <span class="text-gray-500 truncate">{{ truncateText(sc.preview, 40) }}</span>
            </div>
          </template>
          <template v-else-if="step.details.hypothetical_doc_preview">
            <div class="text-xs text-gray-500">{{ truncateText(step.details.hypothetical_doc_preview, 80) }}</div>
          </template>
          <template v-else>
            <div v-for="(val, key) in step.details" :key="key" class="flex gap-1 text-xs py-0.5">
              <span class="text-gray-400">{{ key }}:</span>
              <span class="text-gray-600 break-all">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  thinking: { type: Array, default: () => [] },
  collapsed: { type: Boolean, default: false },
});

defineEmits(['toggle']);

const stageConfig = {
  retrieval: { label: '检索', color: '#B8926E' },
  hyde: { label: 'HyDE', color: '#8B7E6F' },
  reorder: { label: '重排序', color: '#D4914A' },
  summarize: { label: '总结', color: '#7D9B7A' },
};

const getStageLabel = (stage) => stageConfig[stage]?.label || stage || '处理中';
const getStageColor = (stage) => stageConfig[stage]?.color || '#999';

const truncateText = (text, maxLen) => {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
};
</script>
