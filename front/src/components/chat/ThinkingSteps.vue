<template>
  <div v-if="hasPlan || (thinking && thinking.length > 0)" class="mb-2">
    <!-- 检索计划进度（Plan-then-Execute） -->
    <div v-if="hasPlan" class="mb-[var(--van-padding-xs)]">
      <div class="flex items-center justify-between py-1.5 px-[var(--van-padding-xs)] bg-[var(--van-background)] rounded-[var(--van-radius-md)] cursor-pointer select-none"
        @click="$emit('toggle')">
        <span class="text-[var(--van-font-size-sm)] font-medium text-[var(--van-text-color-2)] flex items-center gap-1">
          <ListTodo :size="14" /> 检索进度
          <span class="text-[var(--van-text-color-3)] font-normal">
            {{ planDoneCount }}/{{ plan?.total_steps || plan?.steps.length || 0 }}
          </span>
        </span>
        <span class="text-[var(--van-font-size-sm)] text-[var(--van-text-color-3)]">{{ collapsed ? '展开' : '收起' }}</span>
      </div>
      <div v-show="!collapsed" class="flex flex-col gap-1 mt-1 max-h-60 overflow-y-auto" style="scrollbar-gutter: stable">
        <div v-for="step in plan?.steps" :key="step.id"
          class="flex items-center gap-[var(--van-padding-xs)] py-1.5 px-2 rounded-[var(--van-radius-sm)]"
          :class="step.status === 'in_progress' ? 'bg-[var(--van-primary-color)]/10' : 'bg-[var(--van-background-2)]'">
          <!-- 状态图标 -->
          <span v-if="step.status === 'completed'" class="text-green-500 shrink-0"><CircleCheckBig :size="14" /></span>
          <span v-else-if="step.status === 'in_progress'" class="text-blue-500 shrink-0 animate-spin"><LoaderCircle :size="14" /></span>
          <span v-else class="text-gray-300 shrink-0"><Circle :size="14" /></span>
          <!-- 步骤内容 -->
          <span class="text-[var(--van-font-size-sm)] text-[var(--van-text-color)] truncate">{{ step.content }}</span>
        </div>
      </div>
    </div>

    <!-- 思考过程（原始 thinking 事件，调试用） -->
    <div v-if="thinking && thinking.length > 0 && !hasPlan" class="mb-[var(--van-padding-xs)]">
      <div class="flex items-center justify-between py-1.5 px-[var(--van-padding-xs)] bg-[var(--van-background)] rounded-[var(--van-radius-md)] cursor-pointer select-none"
        @click="$emit('toggle')">
        <span class="text-[var(--van-font-size-sm)] font-medium text-[var(--van-text-color-2)] flex items-center gap-1"><Brain :size="14" /> 思考过程</span>
        <span class="text-[var(--van-font-size-sm)] text-[var(--van-text-color-3)]">{{ collapsed ? '展开' : '收起' }}</span>
      </div>
    </div>

    <!-- 思考过程详细内容（无 plan 时显示） -->
    <div v-show="!collapsed && thinking && thinking.length > 0 && !hasPlan" class="flex flex-col gap-[var(--van-padding-xs)] max-h-60 overflow-y-auto" style="scrollbar-gutter: stable">
      <div v-for="(step, sIndex) in thinking" :key="sIndex"
        class="bg-[var(--van-background-2)] border border-[var(--van-border-color)] rounded-[var(--van-radius-lg)] p-2.5">
        <div class="flex items-center gap-[var(--van-padding-xs)] mb-1">
          <van-tag :color="getStageColor(step.stage)" size="medium" text-color="var(--van-white)">
            {{ getStageLabel(step.stage) }}
          </van-tag>
          <span class="text-[var(--van-font-size-sm)] text-[var(--van-text-color)]">{{ step.content }}</span>
        </div>
        <div v-if="step.details" class="mt-[var(--van-padding-xs)] pl-1">
          <template v-if="step.details.documents">
            <div v-for="(doc, dIndex) in step.details.documents.slice(0, 3)" :key="dIndex"
              class="flex items-center justify-between text-[var(--van-font-size-sm)] py-0.5">
              <span class="text-[var(--van-text-color-2)] truncate mr-[var(--van-padding-xs)]">{{ doc.source }}</span>
              <span v-if="doc.score !== undefined && doc.score !== null" class="text-[var(--van-text-color-3)] shrink-0">
                {{ (doc.score * 100).toFixed(0) }}%
              </span>
            </div>
            <div v-if="step.details.documents.length > 3" class="text-[var(--van-font-size-sm)] text-[var(--van-text-color-3)] mt-1">
              ... 还有 {{ step.details.documents.length - 3 }} 个文档
            </div>
          </template>
          <template v-else-if="step.details.scores">
            <div v-for="(sc, cIndex) in step.details.scores.slice(0, 3)" :key="cIndex"
              class="flex items-center gap-[var(--van-padding-xs)] text-[var(--van-font-size-sm)] py-0.5">
              <span class="text-[var(--van-text-color-3)]">#{{ sc.rank || sc.index }}</span>
              <span class="text-[var(--van-text-color-2)]">{{ (sc.score * 100).toFixed(0) }}%</span>
              <span class="text-[var(--van-text-color-2)] truncate">{{ truncateText(sc.preview, 40) }}</span>
            </div>
          </template>
          <template v-else-if="step.details.hypothetical_doc_preview">
            <div class="text-[var(--van-font-size-sm)] text-[var(--van-text-color-2)]">{{ truncateText(step.details.hypothetical_doc_preview, 80) }}</div>
          </template>
          <template v-else>
            <div v-for="(val, key) in step.details" :key="key" class="flex gap-1 text-[var(--van-font-size-sm)] py-0.5">
              <span class="text-[var(--van-text-color-3)]">{{ key }}:</span>
              <span class="text-[var(--van-text-color-2)] break-all">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Brain, Circle, CircleCheckBig, ListTodo, LoaderCircle } from '@lucide/vue';
import { computed } from 'vue';
import type { AgentPlan, ThinkingStep } from '../../types';

const props = defineProps<{
  thinking: ThinkingStep[];
  collapsed: boolean;
  plan?: AgentPlan;
}>();

defineEmits<{
  toggle: [];
}>();

const hasPlan = computed(() => !!(props.plan && props.plan.steps?.length));

const planDoneCount = computed(() => {
  if (!props.plan?.steps) return 0;
  return props.plan.steps.filter((s) => s.status === 'completed').length;
});

const stageConfig: Record<string, { label: string; color: string }> = {
  retrieval: { label: '检索', color: '#B8926E' },
  hyde: { label: 'HyDE', color: '#8B7E6F' },
  reorder: { label: '重排序', color: '#D4914A' },
  summarize: { label: '总结', color: '#7D9B7A' },
};

const getStageLabel = (stage: string): string => stageConfig[stage]?.label || stage || '处理中';
const getStageColor = (stage: string): string => stageConfig[stage]?.color || 'var(--van-text-color-3)';

const truncateText = (text: string, maxLen: number): string => {
  if (!text) return '';
  return text.length > maxLen ? `${text.slice(0, maxLen)}...` : text;
};
</script>
