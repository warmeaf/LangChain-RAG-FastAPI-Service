<template>
  <div>
    <van-nav-bar :title="$t('knowledgebase.title')" fixed placeholder />

    <div class="flex flex-col gap-4 px-4 mt-4">
      <!-- 文件上传区域 -->
      <div
        class="flex flex-col items-center gap-2 py-8 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer"
        @click="openFilePicker" @dragover.prevent @drop.prevent="handleDrop">
        <van-icon name="upgrade" size="40" color="var(--van-gray-5)" />
        <p class="m-0 text-sm text-gray-600">{{ $t('knowledgebase.uploadText') }}</p>
        <p class="m-0 text-xs text-gray-400">{{ $t('knowledgebase.uploadHint') }}</p>
        <input ref="fileInput" type="file" multiple accept=".md,.txt,.pdf,.docx,.pptx" class="hidden"
          @change="handleFileSelect" />
      </div>

      <!-- 已选文件列表 -->
      <div v-if="selectedFiles.length > 0">
        <h3 class="text-base font-semibold m-0 mb-2">{{ $t('knowledgebase.selectedFiles') }}</h3>
        <van-cell-group inset>
          <van-cell v-for="(file, index) in selectedFiles" :key="index" :title="file.name"
            :value="formatFileSize(file.size)" is-link @click="removeFile(index)">
            <template #right-icon>
              <van-icon name="delete" color="var(--van-danger-color)" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>

      <!-- 上传按钮 -->
      <van-button v-if="selectedFiles.length > 0 && !uploading" type="primary" block size="large" @click="uploadFiles">
        {{ $t('knowledgebase.uploadButton') }}
      </van-button>

      <!-- 上传进度 -->
      <div v-if="uploading" class="flex flex-col gap-3">
        <h3 class="text-base font-semibold m-0">{{ $t('knowledgebase.uploadProgress') }}</h3>
        <div v-for="(progress, index) in uploadProgressList" :key="index" class="flex flex-col gap-1">
          <div class="flex items-center justify-between">
            <span class="text-sm truncate">{{ progress.filename }}</span>
            <van-tag :type="getStatusType(progress.status)" size="medium">
              {{ getStatusText(progress.status) }}
            </van-tag>
          </div>
          <van-progress :percentage="progress.percentage" v-if="progress.percentage !== null" />
          <p class="m-0 text-xs text-gray-500">{{ progress.message }}</p>
        </div>
        <div v-if="uploadComplete" class="flex flex-col items-center gap-2 py-4">
          <van-icon name="success" size="32" color="var(--van-success-color)" />
          <p class="m-0 font-medium">{{ $t('knowledgebase.uploadComplete') }}</p>
          <p class="m-0 text-sm text-gray-500">{{ successCount }} {{ $t('knowledgebase.success') }}, {{ failedCount }}
            {{
              $t('knowledgebase.failed') }}</p>
        </div>
      </div>

      <!-- 文档列表 -->
      <div v-if="!uploading" class="flex flex-col gap-3">
        <div class="flex items-center justify-between">
          <div class="flex items-baseline gap-2">
            <h3 class="text-base font-semibold m-0">{{ $t('knowledgebase.documentList') }}</h3>
            <span class="text-sm text-gray-500">{{ documents.length }} {{ $t('knowledgebase.total') }}</span>
          </div>
          <div class="flex items-center gap-2">
            <van-button v-if="documents.length > 0" size="small" type="danger" plain @click="handleCleanAll">
              {{ $t('knowledgebase.cleanAll') }}
            </van-button>
          </div>
        </div>

        <van-cell-group inset v-if="documents.length > 0">
          <van-cell v-for="doc in documents" :key="doc.id" :title="doc.original_filename || doc.filename" center is-link
            @click="showDocumentActions(doc)">
            <template #icon>
              <van-icon :name="getFileIcon(doc.original_filename || doc.filename)" size="18" class="mr-2" />
            </template>
            <template #label>
              <span>{{ doc.chunk_count }} {{ $t('knowledgebase.chunks') }}</span>
            </template>
          </van-cell>
        </van-cell-group>

        <van-empty v-else-if="!loadingDocuments" :description="$t('knowledgebase.empty')" />

        <van-loading v-if="loadingDocuments" class="flex justify-center py-8" />
      </div>
    </div>

    <!-- 文档操作菜单 -->
    <van-action-sheet v-model:show="showActions" :actions="documentActions"
      :title="currentDocument?.original_filename || currentDocument?.filename" @select="onActionSelect"
      cancel-text="取消" />

    <!-- 文档详情弹窗 -->
    <van-popup v-model:show="showDetail" position="bottom" :style="{ height: '70%' }" round closeable>
      <div class="flex flex-col h-full">
        <div class="flex items-center justify-between px-4 py-3">
          <h4 class="m-0 text-base font-semibold">{{ $t('knowledgebase.documentContent') }}</h4>
        </div>
        <div class="flex-1 overflow-y-auto px-4 py-3">
          <van-loading v-if="loadingDetail" class="flex justify-center py-8" />
          <template v-else>
            <div class="text-sm text-gray-500 mb-3">
              <span>{{ currentDocument?.chunk_count }} {{ $t('knowledgebase.chunks') }}</span>
            </div>
            <div class="flex flex-col gap-4">
              <div class="whitespace-pre-wrap text-sm leading-relaxed">{{ currentDocument?.content ||
                currentDocument?.preview }}</div>
              <div v-for="group in detailPageImages" :key="group.page" class="flex flex-col gap-2">
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

    <!-- 切片列表弹窗 -->
    <van-popup v-model:show="showChunks" position="bottom" :style="{ height: '70%' }" round closeable>
      <div class="flex flex-col h-full">
        <div class="flex items-center justify-between px-4 py-3">
          <h4 class="m-0 text-base font-semibold">{{ $t('knowledgebase.chunkList') }}</h4>
        </div>
        <div class="flex-1 overflow-y-auto px-4 py-3">
          <van-loading v-if="loadingChunks" class="flex justify-center py-8" />
          <template v-else>
            <div class="flex items-center justify-between mb-3 text-sm text-gray-500">
              <span>{{ currentDocument?.filename }}</span>
              <span>{{ totalChunks }} {{ $t('knowledgebase.chunks') }}</span>
            </div>
            <div class="flex flex-col gap-3">
              <div v-for="chunk in chunks" :key="chunk.chunk_id"
                class="border border-gray-100 rounded-lg p-3 flex flex-col gap-2">
                <div class="text-xs text-gray-400">#{{ chunk.index + 1 }}</div>
                <div class="text-sm leading-relaxed whitespace-pre-wrap">{{ chunk.content }}</div>
                <div v-if="chunk._imageUrls && chunk._imageUrls.length > 0" class="flex flex-wrap gap-2">
                  <van-image v-for="(url, idx) in chunk._imageUrls" :key="idx" :src="url" fit="contain"
                    class="max-w-full" />
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </van-popup>
    <tab-bar />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { showToast, showDialog } from 'vant';
import { useI18n } from 'vue-i18n';
import { useUserStore } from '../store/user';
import TabBar from '../components/TabBar.vue';
// 图片鉴权钩子：负责获取带 token 的图片URL，或通过 /images/all/{md5} 缓存全部 base64 图片
import { useAuthImage } from '../composables/useAuthImage';

const router = useRouter();
const { t } = useI18n();
const userStore = useUserStore();

const fileInput = ref(null);
const selectedFiles = ref([]);
const uploading = ref(false);
const uploadProgressList = ref([]);
const uploadComplete = ref(false);
const successCount = ref(0);
const failedCount = ref(0);

const documents = ref([]);
const loadingDocuments = ref(false);
const showDetail = ref(false);
const showChunks = ref(false);
const currentDocument = ref(null);
const loadingDetail = ref(false);
const loadingChunks = ref(false);
const chunks = ref([]);
const totalChunks = ref(0);
const detailPageImages = ref([]);

const { getAllImages, resolveImageUrls } = useAuthImage();

// 将文档详情接口返回的图片URL列表按页分组（图片命名规则：p{page}_i{index}.{ext}），
// 然后从批量图片缓存（imageMap）中查找对应的 base64 data URL
const groupImagesByPage = (imagePaths, imageMap) => {
  const pageMap = {};
  const pageOrder = [];

  for (const path of imagePaths) {
    const filename = path.split('/').pop();
    const match = filename.match(/^p(\d+)_i/);
    const page = match ? parseInt(match[1]) : 0;
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

const showActions = ref(false);
const documentActions = ref([
  { name: '查看内容', action: 'viewContent' },
  { name: '查看切片', action: 'viewChunks' },
  { name: '删除文档', action: 'deleteDoc', color: '#ee0a24' }
]);


const openFilePicker = () => {
  fileInput.value?.click();
};

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files);
  selectedFiles.value = [...selectedFiles.value, ...files];
  event.target.value = '';
};

const handleDrop = (event) => {
  const files = Array.from(event.dataTransfer.files);
  selectedFiles.value = [...selectedFiles.value, ...files];
};

const removeFile = (index) => {
  selectedFiles.value.splice(index, 1);
};

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

const getFileIcon = (filename) => {
  const ext = filename?.split('.').pop()?.toLowerCase();
  const icons = {
    pdf: 'bookmark-o',
    doc: 'description',
    docx: 'description',
    txt: 'notes-o',
    md: 'orders-o',
    ppt: 'chart-trending-o',
    pptx: 'chart-trending-o',
  };
  return icons[ext] || 'notes-o';
};

const uploadFiles = async () => {
  if (selectedFiles.value.length === 0) {
    showToast(t('knowledgebase.noFiles'));
    return;
  }

  const token = userStore.token;
  if (!token) {
    showToast(t('common.login'));
    router.push('/login');
    return;
  }

  uploading.value = true;
  uploadComplete.value = false;
  uploadProgressList.value = [];
  successCount.value = 0;
  failedCount.value = 0;

  const formData = new FormData();
  selectedFiles.value.forEach((file) => {
    formData.append('files', file);
    uploadProgressList.value.push({
      filename: file.name,
      percentage: 0,
      status: 'processing',
      message: t('knowledgebase.starting')
    });
  });

  try {
    const response = await fetch('/knowledge/add/multiple/stream', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });

    if (!response.ok) {
      throw new Error('Upload failed');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const event of events) {
        if (!event.trim()) continue;
        parseEvent(event);
      }
    }
  } catch (error) {
    console.error('Upload error:', error);
    showToast(t('knowledgebase.uploadError'));
    uploadProgressList.value.forEach((item) => {
      if (item.status !== 'completed') {
        item.status = 'failed';
        item.message = t('knowledgebase.uploadError');
      }
    });
    failedCount.value = uploadProgressList.value.filter(p => p.status === 'failed').length;
  } finally {
    uploading.value = false;
    uploadComplete.value = true;
    await fetchDocuments();
    selectedFiles.value = [];
  }
};

const parseEvent = (event) => {
  const lines = event.split('\n');
  let data = '';

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      data = line.substring(6);
    }
  }

  try {
    const eventData = JSON.parse(data);
    const { event_type, filename, message, progress, success_count, failed_count } = eventData;

    if (filename) {
      const index = uploadProgressList.value.findIndex(p => p.filename === filename);
      if (index !== -1) {
        uploadProgressList.value[index].message = message;

        if (event_type === 'completed') {
          uploadProgressList.value[index].status = 'completed';
          uploadProgressList.value[index].percentage = 100;
          successCount.value++;
        } else if (event_type === 'processing') {
          uploadProgressList.value[index].status = 'processing';
          if (progress !== undefined) {
            uploadProgressList.value[index].percentage = progress;
          }
        }
      }
    } else if (event_type === 'finish') {
      successCount.value = success_count;
      failedCount.value = failed_count;
    }
  } catch (e) {
    console.error('Parse event error:', e);
  }
};

const fetchDocuments = async () => {
  const token = userStore.token;
  if (!token) {
    return;
  }

  loadingDocuments.value = true;
  try {
    const response = await fetch('/knowledge/list', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json'
      }
    });

    if (response.ok) {
      const result = await response.json();
      if (result.code === 200 && result.data) {
        documents.value = result.data.documents || [];
      }
    } else {
      console.error('Failed to fetch documents');
    }
  } catch (error) {
    console.error('Fetch documents error:', error);
  } finally {
    loadingDocuments.value = false;
  }
};

const fetchDocumentDetail = async (filename) => {
  const token = userStore.token;
  if (!token) {
    return;
  }

  loadingDetail.value = true;
  try {
    const response = await fetch(`/knowledge/detail?filename=${encodeURIComponent(filename)}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json'
      }
    });

    if (response.ok) {
      const result = await response.json();
      if (result.code === 200 && result.data) {
        return result.data;
      }
    } else {
      console.error('Failed to fetch document detail');
    }
  } catch (error) {
    console.error('Fetch document detail error:', error);
  } finally {
    loadingDetail.value = false;
  }
};

const fetchDocumentChunks = async (filename) => {
  const token = userStore.token;
  if (!token) {
    return;
  }

  loadingChunks.value = true;
  chunks.value = [];
  totalChunks.value = 0;
  try {
    const response = await fetch(`/knowledge/chunks?filename=${encodeURIComponent(filename)}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json'
      }
    });

    if (response.ok) {
      const result = await response.json();
      if (result.code === 200 && result.data) {
        chunks.value = result.data.chunks || [];
        totalChunks.value = result.data.total_chunks || 0;
      }
    } else {
      console.error('Failed to fetch document chunks');
    }
  } catch (error) {
    console.error('Fetch document chunks error:', error);
  } finally {
    loadingChunks.value = false;
  }
};

/** 与列表展示一致：优先 original_filename，否则 filename（后端按文件名删 MD5 与向量文档） */
const deleteDocumentByFilename = async (filename) => {
  const token = userStore.token;
  if (!token || !filename) {
    return false;
  }

  try {
    const qs = new URLSearchParams({
      filename,
      delete_documents: 'true',
    });
    const response = await fetch(
      `/knowledge/delete/filename?${qs.toString()}`,
      {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        },
      }
    );

    if (response.ok) {
      const result = await response.json();
      if (result.code === 200) {
        return true;
      }
    } else {
      console.error('Failed to delete document');
    }
  } catch (error) {
    console.error('Delete document error:', error);
  }
  return false;
};

const handleDeleteDocument = (doc) => {
  return new Promise((resolve) => {
    showDialog({
      title: t('common.confirm'),
      message: t('knowledgebase.deleteConfirm', { filename: doc.original_filename || doc.filename }),
      showCancelButton: true,
    }).then(async (result) => {
      if (result) {
        const filename = doc.original_filename || doc.filename;
        const success = await deleteDocumentByFilename(filename);
        if (success) {
          showToast(t('knowledgebase.deleteSuccess'));
          await fetchDocuments();
        } else {
          showToast(t('knowledgebase.deleteFailed'));
        }
      }
      resolve();
    }).catch(() => {
      resolve();
    });
  });
};

const cleanAllVectors = async () => {
  const token = userStore.token;
  if (!token) {
    return;
  }

  try {
    const response = await fetch('/knowledge/clean', {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json'
      }
    });

    if (response.ok) {
      showToast(t('knowledgebase.cleanSuccess'));
      await fetchDocuments();
    } else {
      showToast(t('knowledgebase.cleanFailed'));
    }
  } catch (error) {
    console.error('Clean vectors error:', error);
    showToast(t('knowledgebase.cleanFailed'));
  }
};

const handleCleanAll = () => {
  showDialog({
    title: t('common.confirm'),
    message: t('knowledgebase.cleanConfirm'),
    showCancelButton: true,
  }).then(async (action) => {
    if (action === 'confirm') {
      await cleanAllVectors();
    }
  });
};

// 批量加载切片图片：一次请求 /images/all/{md5} 拿到所有图片的 base64 缓存，
// 然后给每个切片的 chunk.images 转换为可直接显示的 _imageUrls
// 这样做的目的是减少请求次数（不需要每张图片都发一次 HTTP 请求）
const loadChunkImages = async (chunksList, md5) => {
  if (!md5) return;
  const imageMap = await getAllImages(md5);
  for (const chunk of chunksList) {
    if (chunk.images?.length) {
      chunk._imageUrls = resolveImageUrls(chunk.images, imageMap);
    }
  }
};

const viewDocumentDetail = async (doc) => {
  currentDocument.value = doc;
  detailPageImages.value = [];

  const detail = await fetchDocumentDetail(doc.filename);
  if (detail) {
    currentDocument.value = detail;
    if (detail.md5 && detail.images?.length) {
      const imageMap = await getAllImages(detail.md5);
      detailPageImages.value = groupImagesByPage(detail.images, imageMap);
    }
  }
  showDetail.value = true;
};

const showDocumentActions = (doc) => {
  currentDocument.value = doc;
  showActions.value = true;
};

const onActionSelect = async (action) => {
  showActions.value = false;

  switch (action.action) {
    case 'viewContent':
      detailPageImages.value = [];
      const detail = await fetchDocumentDetail(currentDocument.value.filename);
      if (detail) {
        currentDocument.value = detail;
        if (detail.md5 && detail.images?.length) {
          const imageMap = await getAllImages(detail.md5);
          detailPageImages.value = groupImagesByPage(detail.images, imageMap);
        }
      }
      showDetail.value = true;
      break;
    case 'viewChunks':
      showChunks.value = true;
      await fetchDocumentChunks(currentDocument.value.filename);
      await loadChunkImages(chunks.value, currentDocument.value.md5);
      break;
    case 'deleteDoc':
      await handleDeleteDocument(currentDocument.value);
      break;
  }
};

const getStatusType = (status) => {
  switch (status) {
    case 'completed': return 'success';
    case 'failed': return 'danger';
    default: return 'warning';
  }
};

const getStatusText = (status) => {
  switch (status) {
    case 'completed': return t('knowledgebase.completed');
    case 'failed': return t('knowledgebase.failed');
    default: return t('knowledgebase.processing');
  }
};

onMounted(() => {
  fetchDocuments();
});
</script>
