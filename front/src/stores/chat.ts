import { defineStore } from 'pinia'
import { ref } from 'vue'

interface Message { role: 'user' | 'assistant'; content: string; pipeline?: boolean }

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const sessionId = ref('')
  function addMessage(role: 'user' | 'assistant', content: string, pipeline = false) {
    messages.value.push({ role, content, pipeline })
  }
  return { messages, sessionId, addMessage }
})
