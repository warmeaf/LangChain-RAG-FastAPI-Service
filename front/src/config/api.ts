export interface ApiEndpoints {
  login: string;
  logout: string;
  register: string;
  profile: string;
  uploadFile: string;
  agentQuery: string;
  agentQueryStream: string;
  ragQuery: string;
  getSession: string;
  deleteSession: string;
  getAllSessions: string;
  getUserSessions: string;
  getSessionThinking: string;
  uploadSingleFile: string;
  uploadMultipleFiles: string;
  cleanVectors: string;
  reorderDocuments: string;
}

export interface ApiConfig {
  baseURL: string;
  userBaseURL: string;
  endpoints: ApiEndpoints;
}

export const apiConfig: ApiConfig = {
  baseURL: (import.meta as ImportMeta).env.VITE_BASE_URL || '',
  userBaseURL: (import.meta as ImportMeta).env.VITE_USER_BASE_URL || '',
  endpoints: {
    login: '/user/login/',
    logout: '/user/logout/',
    register: '/user/register/',
    profile: '/user/detail/',
    uploadFile: '/file/upload/',
    agentQuery: '/chat/agent/query/stream',
    agentQueryStream: '/chat/agent/query/stream',
    ragQuery: '/chat/rag/query',
    getSession: '/chat/session/',
    deleteSession: '/chat/session/',
    getAllSessions: '/chat/sessions',
    getUserSessions: '/chat/sessions',
    getSessionThinking: '/chat/session/',
    uploadSingleFile: '/knowledge/add/single',
    uploadMultipleFiles: '/knowledge/add/multiple',
    cleanVectors: '/knowledge/clean',
    reorderDocuments: '/chat/reorder',
  },
};
