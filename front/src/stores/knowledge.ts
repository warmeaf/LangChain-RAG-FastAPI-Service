import { defineStore } from 'pinia';
import { ref } from 'vue';
export interface FileInfo {
  filename: string;
  original_filename: string;
  chunk_count: number;
  created_at: string;
}
export const useKnowledgeStore = defineStore('knowledge', () => {
  const files = ref<FileInfo[]>([]);
  return { files };
});
