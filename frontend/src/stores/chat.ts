import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchHistory, fetchThreadMessages, streamChat } from '@/api/chat'
import type { ChatMessage, ConversationItem } from '@/api/chat'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const conversations = ref<ConversationItem[]>([])
  const currentThreadId = ref<string | null>(null)
  const loading = ref(false)

  /** 加载历史会话列表 */
  async function loadHistory() {
    conversations.value = await fetchHistory()
  }

  /** 切换到已有会话，并从后端加载历史消息 */
  async function selectConversation(threadId: string) {
    if (currentThreadId.value === threadId) return
    currentThreadId.value = threadId
    messages.value = []
    loading.value = true
    try {
      messages.value = await fetchThreadMessages(threadId)
    } finally {
      loading.value = false
    }
  }

  /** 新建对话 */
  function newConversation() {
    currentThreadId.value = null
    messages.value = []
  }

  /** 发送消息（SSE 流式） */
  async function sendMessage(content: string) {
    if (loading.value || !content.trim()) return

    // 推入用户消息
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      content: content.trim(),
    })

    // 预占助手消息气泡
    const assistantId = crypto.randomUUID()
    messages.value.push({
      id: assistantId,
      role: 'assistant',
      content: '',
      loading: true,
    })

    loading.value = true
    const assistantMsg = messages.value.find((m) => m.id === assistantId)!

    await streamChat(content.trim(), currentThreadId.value, {
      onConversation(threadId) {
        // 后端每次都会发送 conversation 事件（含已有会话），只在新会话时插入列表
        const isNew = !conversations.value.find((c) => c.key === threadId)
        currentThreadId.value = threadId
        if (isNew) {
          // label 先占位，fetchHistory 刷新后会替换为 initial_prompt
          const firstUserMsg = messages.value.find((m) => m.role === 'user')
          const label = firstUserMsg
            ? firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '…' : '')
            : threadId.slice(0, 8)
          conversations.value.unshift({
            key: threadId,
            label,
            timestamp: Date.now(),
          })
        }
      },
      onChunk(chunk) {
        assistantMsg.loading = false
        assistantMsg.content += chunk
      },
      onDone() {
        assistantMsg.loading = false
        loading.value = false
      },
      onError(err) {
        assistantMsg.loading = false
        assistantMsg.content = `请求失败：${err.message}`
        loading.value = false
      },
    })
  }

  return {
    messages,
    conversations,
    currentThreadId,
    loading,
    loadHistory,
    selectConversation,
    newConversation,
    sendMessage,
  }
})
