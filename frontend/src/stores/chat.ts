import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  deleteSession as deleteSessionRequest,
  fetchSessionMessages,
  fetchSessions,
  resumeChat,
  streamChat,
} from '@/api/chat'
import type { ChatMessage, SessionItem, StreamCallbacks } from '@/api/chat'
import type { InterruptData, ResumePayload } from '@/types/agent'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const sessions = ref<SessionItem[]>([])
  const currentThreadId = ref<string | null>(null)
  const loading = ref(false)
  const pendingInterrupt = ref<InterruptData | null>(null)
  const abortController = ref<AbortController | null>(null)

  function appendLoadingAssistant(): ChatMessage {
    const message: ChatMessage = {
      id: `loading:${crypto.randomUUID()}`,
      kind: 'assistant',
      role: 'assistant',
      content: '',
      loading: true,
    }
    messages.value.push(message)
    return message
  }

  function takeLoadingAssistant(): ChatMessage | undefined {
    return messages.value.find(
      (message) => message.kind === 'assistant' && message.loading === true,
    )
  }

  function removeLoadingAssistant() {
    messages.value = messages.value.filter(
      (message) => !(message.kind === 'assistant' && message.loading === true),
    )
  }

  function keepLoadingAssistantLast() {
    const loadingAssistant = takeLoadingAssistant()
    if (!loadingAssistant) {
      appendLoadingAssistant()
      return
    }
    const index = messages.value.indexOf(loadingAssistant)
    if (index === messages.value.length - 1) return
    messages.value.splice(index, 1)
    messages.value.push(loadingAssistant)
  }

  async function loadSessions() {
    sessions.value = await fetchSessions()
  }

  async function selectSession(threadId: string) {
    if (currentThreadId.value === threadId) return
    currentThreadId.value = threadId
    messages.value = []
    pendingInterrupt.value = null
    loading.value = true
    try {
      messages.value = await fetchSessionMessages(threadId)
    } finally {
      loading.value = false
    }
  }

  function newSession() {
    currentThreadId.value = null
    messages.value = []
    pendingInterrupt.value = null
  }

  async function deleteSession(threadId: string) {
    if (loading.value && currentThreadId.value === threadId) return

    await deleteSessionRequest(threadId)
    sessions.value = sessions.value.filter((session) => session.key !== threadId)
    if (currentThreadId.value === threadId) newSession()
  }

  function cancelStream() {
    abortController.value?.abort()
    abortController.value = null
    loading.value = false
    removeLoadingAssistant()
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
    appendLoadingAssistant()
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
    appendLoadingAssistant()
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
      onSession(threadId) {
        const isNew = !sessions.value.some((session) => session.key === threadId)
        currentThreadId.value = threadId
        if (!isNew) return
        const firstUserMessage = messages.value.find((message) => message.kind === 'user')
        const label = firstUserMessage
          ? firstUserMessage.content.slice(0, 30) +
            (firstUserMessage.content.length > 30 ? '...' : '')
          : threadId.slice(0, 8)
        sessions.value.unshift({ key: threadId, label, timestamp: Date.now() })
      },
      onChunk(chunk, messageId, agentName, namespace) {
        const existing = messages.value.find((message) => message.id === messageId)
        if (existing) {
          existing.content += chunk
          existing.loading = false
          existing.namespace = namespace
          return
        }
        const loadingAssistant = takeLoadingAssistant()
        if (loadingAssistant) {
          Object.assign(loadingAssistant, {
            id: messageId,
            content: chunk,
            loading: false,
            actorName: agentName,
            namespace,
          })
          return
        }
        messages.value.push({
          id: messageId,
          kind: 'assistant',
          role: 'assistant',
          content: chunk,
          actorName: agentName,
          namespace,
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
        keepLoadingAssistantLast()
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
        keepLoadingAssistantLast()
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
        keepLoadingAssistantLast()
      },
      onInterrupt(data) {
        const interruptMessage: ChatMessage = {
          id: `interrupt:${data.interrupt_id ?? crypto.randomUUID()}`,
          kind: 'assistant',
          role: 'assistant',
          content: '',
          interrupted: data,
        }
        const loadingAssistant = takeLoadingAssistant()
        if (loadingAssistant) Object.assign(loadingAssistant, interruptMessage, { loading: false })
        else upsertMessage(interruptMessage)
        pendingInterrupt.value = data
      },
      onDone() {
        removeLoadingAssistant()
        loading.value = false
        abortController.value = null
      },
      onError(error) {
        const errorMessage: ChatMessage = {
          id: crypto.randomUUID(),
          kind: 'assistant',
          role: 'assistant',
          content: `Request failed: ${error.message}`,
        }
        const loadingAssistant = takeLoadingAssistant()
        if (loadingAssistant) Object.assign(loadingAssistant, errorMessage, { loading: false })
        else messages.value.push(errorMessage)
        loading.value = false
        abortController.value = null
      },
      signal: abortController.value?.signal,
    }
  }

  return {
    messages,
    sessions,
    currentThreadId,
    loading,
    pendingInterrupt,
    loadSessions,
    selectSession,
    newSession,
    deleteSession,
    sendMessage,
    cancelStream,
    resumeApprove,
    resumeReject,
    resumeInput,
  }
})
