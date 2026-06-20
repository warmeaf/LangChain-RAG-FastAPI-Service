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
        <h4 class="m-0 text-base font-semibold">{{ $t('knowledgebase.documentContent') }}</h4>
      </div>
      <div class="flex-1 overflow-y-auto px-4 py-3">
        <van-loading v-if="loading" class="flex justify-center py-8" />
        <template v-else>
          <div class="text-sm text-gray-500 mb-3">
            <span>{{ detail?.chunk_count || document?.chunk_count }} {{ $t('knowledgebase.chunks') }}</span>
          </div>
          <div class="flex flex-col gap-4">
            <div class="whitespace-pre-wrap text-sm leading-relaxed">
              {{ detail?.content || detail?.preview }}
            </div>
            <div v-for="group in pageImages" :key="group.page" class="flex flex-col gap-2">
              <div class="text-xs text-gray-500">第 {{ group.page + 1 }} 页</div>
              <div class="flex flex-wrap gap-2">
                <van-image v-for="(url, i) in group.urls" :key="i" :src="url" fit="contain" class="max-w-full" />
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

interface PageImageGroup {
  page: number;
  urls: string[];
}

type ImageMap = Record<string, string>;

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
const detail = ref<DocumentItem | null>(null);
const pageImages = ref<PageImageGroup[]>([]);

const groupImagesByPage = (imagePaths: string[], imageMap: ImageMap): PageImageGroup[] => {
  const pageMap: Record<number, PageImageGroup> = {};
  const pageOrder: PageImageGroup[] = [];
  for (const path of imagePaths) {
    const filename = path.split('/').pop();
    const match = filename?.match(/^p(\d+)_i/);
    const page = match ? parseInt(match[1], 10) : 0;
    const url = resolveImageUrls([path], imageMap)[0];
    if (!url) continue;
    if (!pageMap[page]) {
      pageMap[page] = { page, urls: [] };
      pageOrder.push(pageMap[page]);
    }
    pageMap[page].urls.push(url);
  }
  return pageOrder;
};

const fetchDetail = async (filename: string): Promise<DocumentItem | null> => {
  const token = userStore.token;
  if (!token) return null;
  try {
    const res = await fetch(`/knowledge/detail?filename=${encodeURIComponent(filename)}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    });
    if (res.ok) {
      const result = (await res.json()) as { code: number; data?: DocumentItem };
      return result.code === 200 && result.data ? result.data : null;
    }
  } catch { /* ignore */ }
  return null;
};

watch(() => props.modelValue, async (show) => {
  if (show && props.document) {
    loading.value = true;
    detail.value = null;
    pageImages.value = [];
    const data = await fetchDetail(props.document.filename);
    if (data) {
      detail.value = data;
      if (data.md5 && data.images?.length) {
        const imageMap = await getAllImages(data.md5);
        pageImages.value = groupImagesByPage(data.images, imageMap);
      }
    }
    loading.value = false;
  }
});
</script>
