import { showToast } from 'vant';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { useUserStore } from '../store/user';
import type { UploadProgress } from '../types';

interface UseKnowledgeUploadReturn {
  fileInput: ReturnType<typeof ref<HTMLInputElement | null>>;
  selectedFiles: ReturnType<typeof ref<File[]>>;
  uploading: ReturnType<typeof ref<boolean>>;
  uploadProgressList: ReturnType<typeof ref<UploadProgress[]>>;
  uploadComplete: ReturnType<typeof ref<boolean>>;
  successCount: ReturnType<typeof ref<number>>;
  failedCount: ReturnType<typeof ref<number>>;
  openFilePicker: () => void;
  handleFileSelect: (event: Event) => void;
  handleDrop: (event: DragEvent) => void;
  removeFile: (index: number) => void;
  formatFileSize: (bytes: number) => string;
  getStatusType: (status: string) => 'success' | 'danger' | 'warning';
  getStatusText: (status: string) => string;
  uploadFiles: () => Promise<void>;
}

export function useKnowledgeUpload(
  onUploadComplete: () => Promise<void>,
): UseKnowledgeUploadReturn {
  const router = useRouter();
  const { t } = useI18n();
  const userStore = useUserStore();

  const fileInput = ref<HTMLInputElement | null>(null);
  const selectedFiles = ref<File[]>([]);
  const uploading = ref(false);
  const uploadProgressList = ref<UploadProgress[]>([]);
  const uploadComplete = ref(false);
  const successCount = ref(0);
  const failedCount = ref(0);

  const openFilePicker = (): void => fileInput.value?.click();

  const handleFileSelect = (event: Event): void => {
    const target = event.target as HTMLInputElement;
    if (target.files) {
      selectedFiles.value = [...selectedFiles.value, ...Array.from(target.files)];
    }
    target.value = '';
  };

  const handleDrop = (event: DragEvent): void => {
    if (event.dataTransfer?.files) {
      selectedFiles.value = [...selectedFiles.value, ...Array.from(event.dataTransfer.files)];
    }
  };

  const removeFile = (index: number): void => {
    selectedFiles.value.splice(index, 1);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusType = (status: string): 'success' | 'danger' | 'warning' => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'danger';
      default:
        return 'warning';
    }
  };

  const getStatusText = (status: string): string => {
    switch (status) {
      case 'completed':
        return t('knowledgebase.completed');
      case 'failed':
        return t('knowledgebase.failed');
      default:
        return t('knowledgebase.processing');
    }
  };

  const parseEvent = (event: string): void => {
    const lines = event.split('\n');
    let data = '';
    for (const line of lines) {
      if (line.startsWith('data: ')) data = line.substring(6);
    }
    try {
      const parsed = JSON.parse(data) as {
        event_type: string;
        filename?: string;
        message?: string;
        progress?: number;
        success_count?: number;
        failed_count?: number;
      };
      const { event_type, filename, message, progress, success_count, failed_count } = parsed;

      if (filename) {
        const index = uploadProgressList.value.findIndex((p) => p.filename === filename);
        if (index !== -1) {
          uploadProgressList.value[index].message = message || '';
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
        successCount.value = success_count || 0;
        failedCount.value = failed_count || 0;
      }
    } catch {
      // ignore parse errors
    }
  };

  const uploadFiles = async (): Promise<void> => {
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

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader');

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
      await onUploadComplete();
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
    getStatusType,
    getStatusText,
    uploadFiles,
  };
}
