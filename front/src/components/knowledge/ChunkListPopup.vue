<template>
  <van-popup
    :show="modelValue"
    position="bottom"
    :style="{ height: '70%' }"
    round
    closeable
    @update:show="$emit('update:modelValue', $event)"
  >
    <div class="flex flex-col h-full">
      <div class="flex items-center justify-between px-4 py-3">
        <h4 class="m-0 text-base font-semibold">{{ $t('knowledgebase.chunkList') }}</h4>
      </div>
      <div class="flex-1 overflow-y-auto px-4 py-3">
        <van-loading v-if="loading" class="flex justify-center py-8" />
        <template v-else>
          <div class="flex items-center justify-between mb-3 text-sm text-gray-500">
            <span>{{ document?.filename }}</span>
            <span>{{ totalChunks }} {{ $t('knowledgebase.chunks') }}</span>
          </div>
          <div class="flex flex-col gap-3">
            <div v-for="chunk in chunks" :key="chunk.chunk_id"
              class="border border-gray-100 rounded-lg p-3 flex flex-col gap-2">
              <div class="text-xs text-gray-400">#{{ chunk.index + 1 }}</div>
              <div class="text-sm leading-relaxed whitespace-pre-wrap">{{ chunk.content }}</div>
              <div v-if="chunk._imageUrls && chunk._imageUrls.length > 0" class="flex flex-wrap gap-2">
                <van-image v-for="(url, idx) in chunk._imageUrls" :key="idx" :src="url" fit="contain" class="max-w-full" />
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useAuthImage } from '../../composables/useAuthImage';
import { useUserStore } from '../../store/user';
import type { DocumentItem } from '../../types';

interface ChunkItem {
  chunk_id: string;
  index: number;
  content: string;
  images?: string[];
  _imageUrls?: string[];
}

interface ImageMap {
  [key: string]: string;
}

const props = defineProps<{
  modelValue: boolean;
  document: DocumentItem | null;
}>();

defineEmits<{
  'update:modelValue': [value: boolean];
}>();

const userStore = useUserStore();
const { getAllImages, resolveImageUrls } = useAuthImage();

const loading = ref(false);
const chunks = ref<ChunkItem[]>([]);
const totalChunks = ref(0);

const fetchChunks = async (filename: string): Promise<void> => {
  const token = userStore.token;
  if (!token) return;
  try {
    const res = await fetch(`/knowledge/chunks?filename=${encodeURIComponent(filename)}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    });
    if (res.ok) {
      const result = (await res.json()) as { code: number; data?: { chunks?: ChunkItem[]; total_chunks?: number } };
      if (result.code === 200 && result.data) {
        chunks.value = result.data.chunks || [];
        totalChunks.value = result.data.total_chunks || 0;
      }
    }
  } catch { /* ignore */ }
};

const loadChunkImages = async (chunksList: ChunkItem[], md5: string): Promise<void> => {
  if (!md5) return;
  const imageMap = await getAllImages(md5) as ImageMap;
  for (const chunk of chunksList) {
    if (chunk.images?.length) {
      chunk._imageUrls = resolveImageUrls(chunk.images, imageMap);
    }
  }
};

watch(() => props.modelValue, async (show) => {
  if (show && props.document) {
    loading.value = true;
    chunks.value = [];
    totalChunks.value = 0;
    await fetchChunks(props.document.filename);
    await loadChunkImages(chunks.value, props.document.md5 || '');
    loading.value = false;
  }
});
</script>
