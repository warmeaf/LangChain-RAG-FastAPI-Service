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

        <van-cell-group v-if="documents.length > 0" class="m-0!" inset>
          <van-cell v-for="doc in documents" :key="doc.id" :title="doc.original_filename || doc.filename" center is-link
             @click="showDocumentActions(doc)">
            <template #icon>
              <div class="flex items-center justify-center w-8 h-8 bg-gray-50 rounded-full mr-2">
                <van-icon :name="getFileIcon(doc.original_filename || doc.filename)" size="16"/>
              </div>
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
    <DocumentDetailPopup v-model="showDetail" :document="currentDocument" />

    <!-- 切片列表弹窗 -->
    <ChunkListPopup v-model="showChunks" :document="currentDocument" />
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
import DocumentDetailPopup from '../components/knowledge/DocumentDetailPopup.vue';
import ChunkListPopup from '../components/knowledge/ChunkListPopup.vue';
import { useKnowledgeUpload } from '../composables/useKnowledgeUpload';

const router = useRouter();
const { t } = useI18n();
const userStore = useUserStore();

const documents = ref([]);
const loadingDocuments = ref(false);
const showDetail = ref(false);
const showChunks = ref(false);
const currentDocument = ref(null);

const showActions = ref(false);
const documentActions = ref([
  { name: '查看内容', action: 'viewContent' },
  { name: '查看切片', action: 'viewChunks' },
  { name: '删除文档', action: 'deleteDoc', color: '#ee0a24' },
]);

// 文档列表（须在 useKnowledgeUpload 之前声明）
const fetchDocuments = async () => {
  const token = userStore.token;
  if (!token) return;
  loadingDocuments.value = true;
  try {
    const response = await fetch('/knowledge/list', {
      headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/json' },
    });
    if (response.ok) {
      const result = await response.json();
      if (result.code === 200 && result.data) {
        documents.value = result.data.documents || [];
      }
    }
  } catch { /* ignore */ } finally {
    loadingDocuments.value = false;
  }
};

// 上传逻辑
const {
  fileInput, selectedFiles,
  uploading, uploadProgressList, uploadComplete, successCount, failedCount,
  openFilePicker, handleFileSelect, handleDrop, removeFile,
  formatFileSize, getFileIcon, getStatusType, getStatusText,
  uploadFiles,
} = useKnowledgeUpload(fetchDocuments);

// 删除文档
const deleteDocumentByFilename = async (filename) => {
  const token = userStore.token;
  if (!token || !filename) return false;
  try {
    const response = await fetch(`/knowledge/delete/filename?${new URLSearchParams({ filename, delete_documents: 'true' })}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    });
    if (response.ok) {
      const result = await response.json();
      if (result.code === 200) return true;
    }
  } catch { /* ignore */ }
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
        const success = await deleteDocumentByFilename(doc.original_filename || doc.filename);
        showToast(success ? t('knowledgebase.deleteSuccess') : t('knowledgebase.deleteFailed'));
        if (success) await fetchDocuments();
      }
      resolve();
    }).catch(() => resolve());
  });
};

// 清空
const cleanAllVectors = async () => {
  const token = userStore.token;
  if (!token) return;
  try {
    const response = await fetch('/knowledge/clean', {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/json' },
    });
    if (response.ok) {
      showToast(t('knowledgebase.cleanSuccess'));
      await fetchDocuments();
    } else {
      showToast(t('knowledgebase.cleanFailed'));
    }
  } catch { showToast(t('knowledgebase.cleanFailed')); }
};

const handleCleanAll = () => {
  showDialog({
    title: t('common.confirm'),
    message: t('knowledgebase.cleanConfirm'),
    showCancelButton: true,
  }).then(async (action) => {
    if (action === 'confirm') await cleanAllVectors();
  });
};

// 文档操作
const showDocumentActions = (doc) => {
  currentDocument.value = doc;
  showActions.value = true;
};

const onActionSelect = async (action) => {
  showActions.value = false;
  switch (action.action) {
    case 'viewContent':
      showDetail.value = true;
      break;
    case 'viewChunks':
      showChunks.value = true;
      break;
    case 'deleteDoc':
      await handleDeleteDocument(currentDocument.value);
      break;
  }
};

onMounted(() => {
  fetchDocuments();
});
</script>
