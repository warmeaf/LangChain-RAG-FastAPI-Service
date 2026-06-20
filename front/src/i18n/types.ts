export interface CommonMessages {
  confirm: string;
  cancel: string;
  back: string;
  loading: string;
  save: string;
  delete: string;
  edit: string;
  search: string;
  notFound: string;
  login: string;
  register: string;
  logout: string;
  allCategories: string;
}

export interface NavMessages {
  home: string;
  aiChat: string;
  sessions: string;
  knowledge: string;
  my: string;
}

export interface CategoryMessages {
  headline: string;
  society: string;
  domestic: string;
  international: string;
  entertainment: string;
  sports: string;
  military: string;
  technology: string;
  finance: string;
  more: string;
}

export interface HomeMessages {
  title: string;
  more: string;
  refresh: string;
  loadMore: string;
  noMore: string;
  categories: CategoryMessages;
}

export interface AiChatMessages {
  title: string;
  placeholder: string;
  send: string;
  thinking: string;
}

export interface MyMessages {
  title: string;
  notLoggedIn: string;
  goToLogin: string;
  goToRegister: string;
  myFavorite: string;
  browsingHistory: string;
  knowledgeBase: string;
  aboutUs: string;
  settings: string;
  logout: string;
  profile: string;
}

export interface SettingsMessages {
  title: string;
  personalization: string;
  themeCustomization: string;
  languageSettings: string;
  account: string;
  privacySettings: string;
  notificationSettings: string;
  aboutUs: string;
  selectTheme: string;
  themeChanged: string;
  languageChanged: string;
  selectLanguage: string;
}

export interface ProfileMessages {
  title: string;
  username: string;
  bio: string;
  save: string;
}

export interface KnowledgeBaseMessages {
  title: string;
  uploadText: string;
  uploadHint: string;
  selectedFiles: string;
  uploadButton: string;
  uploadProgress: string;
  uploadComplete: string;
  success: string;
  failed: string;
  noFiles: string;
  uploadError: string;
  starting: string;
  processing: string;
  completed: string;
  documentList: string;
  documentContent: string;
  viewChunks: string;
  chunkList: string;
  total: string;
  chunks: string;
  empty: string;
  cleanAll: string;
  cleanConfirm: string;
  cleanSuccess: string;
  cleanFailed: string;
  deleteConfirm: string;
  deleteSuccess: string;
  deleteFailed: string;
}

export interface LocaleMessages {
  common: CommonMessages;
  nav: NavMessages;
  home: HomeMessages;
  aiChat: AiChatMessages;
  my: MyMessages;
  settings: SettingsMessages;
  profile: ProfileMessages;
  knowledgebase: KnowledgeBaseMessages;
}
