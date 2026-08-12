import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchHistory, fetchThreadMessages, resumeChat, streamChat } from '@/api/chat'
import type { ChatMessage, ConversationItem, StreamCallbacks } from '@/api/chat'
import type { InterruptData, ResumePayload } from '@/types/agent'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const conversations = ref<ConversationItem[]>([])
  const currentThreadId = ref<string | null>(null)
  const loading = ref(false)
  const pendingInterrupt = ref<InterruptData | null>(null)
  const abortController = ref<AbortController | null>(null)

  async function loadHistory() {
    conversations.value = await fetchHistory()
  }

  async function selectConversation(threadId: string) {
    if (currentThreadId.value === threadId) return
    currentThreadId.value = threadId
    messages.value = []
    pendingInterrupt.value = null
    loading.value = true
    try {
      messages.value = await fetchThreadMessages(threadId)
    } finally {
      loading.value = false
    }
  }

  function newConversation() {
    currentThreadId.value = null
    messages.value = []
    pendingInterrupt.value = null
  }

  function cancelStream() {
    abortController.value?.abort()
    abortController.value = null
    loading.value = false
  }

  async function sendMessage(content: string) {
    if (loading.value || !content.trim()) return

    messages.value.push({
      id: crypto.randomUUID(),
      kind: 'user',
      role: 'user',
      content: content.trim(),
    })

    loading.value = true
    pendingInterrupt.value = null
    abortController.value = new AbortController()
    await streamChat(content.trim(), currentThreadId.value, buildCallbacks())
  }

  async function resumeApprove() {
    if (!pendingInterrupt.value || pendingInterrupt.value.interrupt_mode !== 'approval') return
    await resumeWithData({
      decisions: pendingInterrupt.value.actions.map(() => ({ type: 'approve' as const })),
    })
  }

  async function resumeReject() {
    if (!pendingInterrupt.value || pendingInterrupt.value.interrupt_mode !== 'approval') return
    await resumeWithData({
      decisions: pendingInterrupt.value.actions.map(() => ({ type: 'reject' as const })),
    })
  }

  async function resumeInput(inputText: string) {
    if (!pendingInterrupt.value || pendingInterrupt.value.interrupt_mode !== 'input') return
    if (pendingInterrupt.value.resume_mode === 'value') {
      await resumeWithData(inputText)
      return
    }
    await resumeWithData({
      decisions: pendingInterrupt.value.actions.map(() => ({
        type: 'respond' as const,
        message: inputText,
      })),
    })
  }

  async function resumeWithData(resumeData: ResumePayload) {
    if (!currentThreadId.value) return
    loading.value = true
    pendingInterrupt.value = null
    abortController.value = new AbortController()
    await resumeChat(currentThreadId.value, resumeData, buildCallbacks())
  }

  function upsertMessage(message: ChatMessage): ChatMessage {
    const existing = messages.value.find((item) => item.id === message.id)
    if (existing) {
      Object.assign(existing, message)
      return existing
    }
    messages.value.push(message)
    return message
  }

  function buildCallbacks(): StreamCallbacks {
    return {
      onConversation(threadId) {
        const isNew = !conversations.value.some((conversation) => conversation.key === threadId)
        currentThreadId.value = threadId
        if (!isNew) return
        const firstUserMessage = messages.value.find((message) => message.kind === 'user')
        const label = firstUserMessage
          ? firstUserMessage.content.slice(0, 30) +
            (firstUserMessage.content.length > 30 ? '...' : '')
          : threadId.slice(0, 8)
        conversations.value.unshift({ key: threadId, label, timestamp: Date.now() })
      },
      onChunk(chunk, messageId, agentName) {
        const existing = messages.value.find((message) => message.id === messageId)
        if (existing) {
          existing.content += chunk
          existing.loading = false
          return
        }
        messages.value.push({
          id: messageId,
          kind: 'assistant',
          role: 'assistant',
          content: chunk,
          actorName: agentName,
        })
      },
      onAgentRouting(routing) {
        upsertMessage({
          id: routing.id,
          kind: 'agent_routing',
          content: '',
          actorName: routing.agentName,
          toolCallId: routing.toolCallId,
          targetAgent: routing.targetAgent,
          description: routing.description,
          namespace: routing.namespace,
          eventData: routing.eventData,
        })
      },
      onToolCallStart(calls) {
        for (const call of calls) {
          upsertMessage({
            id: `tool-call:${call.id}`,
            kind: 'tool_call',
            content: '',
            actorName: call.agentName,
            toolCallId: call.id,
            toolName: call.name,
            toolArgs: call.args,
            namespace: call.namespace,
            eventData: call.eventData,
          })
        }
      },
      onToolResult(result) {
        const call = messages.value.find((message) => message.toolCallId === result.tool_call_id)
        if (call) call.status = result.isError ? 'error' : 'success'
        upsertMessage({
          id: result.id,
          kind: 'tool_result',
          content: result.content,
          actorName: result.agentName,
          toolCallId: result.tool_call_id,
          toolName: result.toolName,
          namespace: result.namespace,
          eventData: result.eventData,
        })
      },
      onInterrupt(data) {
        upsertMessage({
          id: `interrupt:${data.interrupt_id ?? crypto.randomUUID()}`,
          kind: 'assistant',
          role: 'assistant',
          content: '',
          interrupted: data,
        })
        pendingInterrupt.value = data
      },
      onDone() {
        loading.value = false
        abortController.value = null
      },
      onError(error) {
        messages.value.push({
          id: crypto.randomUUID(),
          kind: 'assistant',
          role: 'assistant',
          content: `Request failed: ${error.message}`,
        })
        loading.value = false
        abortController.value = null
      },
      signal: abortController.value?.signal,
    }
  }

  return {
    messages,
    conversations,
    currentThreadId,
    loading,
    pendingInterrupt,
    loadHistory,
    selectConversation,
    newConversation,
    sendMessage,
    cancelStream,
    resumeApprove,
    resumeReject,
    resumeInput,
  }
})
