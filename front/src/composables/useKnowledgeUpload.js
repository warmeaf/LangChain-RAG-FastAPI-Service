import { showToast } from 'vant';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { useUserStore } from '../store/user';

/**
 * 知识库文件上传逻辑封装
 * 提取 KnowledgeBase.vue 中的上传流程：文件选择、SSE 流式上传、进度管理
 */
export function useKnowledgeUpload(onUploadComplete) {
  const router = useRouter();
  const { t } = useI18n();
  const userStore = useUserStore();

  // 文件选择
  const fileInput = ref(null);
  const selectedFiles = ref([]);

  // 上传状态
  const uploading = ref(false);
  const uploadProgressList = ref([]);
  const uploadComplete = ref(false);
  const successCount = ref(0);
  const failedCount = ref(0);

  // 文件操作
  const openFilePicker = () => fileInput.value?.click();

  const handleFileSelect = (event) => {
    selectedFiles.value = [...selectedFiles.value, ...Array.from(event.target.files)];
    event.target.value = '';
  };

  const handleDrop = (event) => {
    selectedFiles.value = [...selectedFiles.value, ...Array.from(event.dataTransfer.files)];
  };

  const removeFile = (index) => {
    selectedFiles.value.splice(index, 1);
  };

  // 工具函数
  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

  const getStatusType = (status) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'danger';
      default:
        return 'warning';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'completed':
        return t('knowledgebase.completed');
      case 'failed':
        return t('knowledgebase.failed');
      default:
        return t('knowledgebase.processing');
    }
  };

  // SSE 事件解析
  const parseEvent = (event) => {
    const lines = event.split('\n');
    let data = '';
    for (const line of lines) {
      if (line.startsWith('data: ')) data = line.substring(6);
    }
    try {
      const { event_type, filename, message, progress, success_count, failed_count } =
        JSON.parse(data);
      if (filename) {
        const index = uploadProgressList.value.findIndex((p) => p.filename === filename);
        if (index !== -1) {
          uploadProgressList.value[index].message = message;
          if (event_type === 'completed') {
            uploadProgressList.value[index].status = 'completed';
            uploadProgressList.value[index].percentage = 100;
            successCount.value++;
          } else if (event_type === 'processing') {
            uploadProgressList.value[index].status = 'processing';
            if (progress !== undefined) uploadProgressList.value[index].percentage = progress;
          }
        }
      } else if (event_type === 'finish') {
        successCount.value = success_count;
        failedCount.value = failed_count;
      }
    } catch {
      /* ignore parse errors */
    }
  };

  // SSE 流式上传
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
        message: t('knowledgebase.starting'),
      });
    });

    try {
      const response = await fetch('/knowledge/add/multiple/stream', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!response.ok) throw new Error('Upload failed');

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';
        for (const evt of events) {
          if (evt.trim()) parseEvent(evt);
        }
      }
    } catch {
      showToast(t('knowledgebase.uploadError'));
      uploadProgressList.value.forEach((item) => {
        if (item.status !== 'completed') {
          item.status = 'failed';
          item.message = t('knowledgebase.uploadError');
        }
      });
      failedCount.value = uploadProgressList.value.filter((p) => p.status === 'failed').length;
    } finally {
      uploading.value = false;
      uploadComplete.value = true;
      if (onUploadComplete) await onUploadComplete();
      selectedFiles.value = [];
    }
  };

  return {
    fileInput,
    selectedFiles,
    uploading,
    uploadProgressList,
    uploadComplete,
    successCount,
    failedCount,
    openFilePicker,
    handleFileSelect,
    handleDrop,
    removeFile,
    formatFileSize,
    getFileIcon,
    getStatusType,
    getStatusText,
    uploadFiles,
  };
}
