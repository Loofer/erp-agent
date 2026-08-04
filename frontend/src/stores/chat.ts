import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchHistory, fetchThreadMessages, streamChat, resumeChat } from '@/api/chat'
import type { ChatMessage, ConversationItem, StreamCallbacks } from '@/api/chat'
import { namespaceKey } from '@/types/agent'
import type { AgentNode, InterruptData, ResumePayload } from '@/types/agent'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const conversations = ref<ConversationItem[]>([])
  const currentThreadId = ref<string | null>(null)
  const loading = ref(false)
  const pendingInterrupt = ref<InterruptData | null>(null)
  const abortController = ref<AbortController | null>(null)

  /** 加载历史会话列表 */
  async function loadHistory() {
    conversations.value = await fetchHistory()
  }

  /** 切换到已有会话，并从后端加载历史消息 */
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

  /** 新建对话 */
  function newConversation() {
    currentThreadId.value = null
    messages.value = []
    pendingInterrupt.value = null
  }

  /** 取消当前正在进行的流 */
  function cancelStream() {
    abortController.value?.abort()
    abortController.value = null
    loading.value = false
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
      executionNodes: [],
    })

    loading.value = true
    pendingInterrupt.value = null
    abortController.value = new AbortController()

    const assistantMsg = messages.value.find((m) => m.id === assistantId)!
    const callbacks = _buildCallbacks(assistantMsg)

    await streamChat(content.trim(), currentThreadId.value, callbacks)
  }

  /** HITL 审批型 — 批准 */
  async function resumeApprove() {
    if (!pendingInterrupt.value || pendingInterrupt.value.interrupt_mode !== 'approval') return
    await _resumeWithData({
      decisions: pendingInterrupt.value.actions.map(() => ({ type: 'approve' as const })),
    })
  }

  /** HITL 审批型 — 拒绝 */
  async function resumeReject() {
    if (!pendingInterrupt.value || pendingInterrupt.value.interrupt_mode !== 'approval') return
    await _resumeWithData({
      decisions: pendingInterrupt.value.actions.map(() => ({ type: 'reject' as const })),
    })
  }

  /** HITL 输入型 — 提交补充数据 */
  async function resumeInput(inputText: string) {
    if (!pendingInterrupt.value || pendingInterrupt.value.interrupt_mode !== 'input') return
    await _resumeWithData({
      decisions: pendingInterrupt.value.actions.map(() => ({
        type: 'respond' as const,
        message: inputText,
      })),
    })
  }

  /** 内部：调用 resume 接口继续会话 */
  async function _resumeWithData(resumeData: ResumePayload) {
    if (!currentThreadId.value) return

    let assistantMsg = messages.value[messages.value.length - 1]
    if (!assistantMsg || assistantMsg.role !== 'assistant') {
      assistantMsg = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        executionNodes: [],
      }
      messages.value.push(assistantMsg)
    }
    assistantMsg.loading = true
    assistantMsg.interrupted = undefined

    loading.value = true
    pendingInterrupt.value = null
    abortController.value = new AbortController()

    const callbacks = _buildCallbacks(assistantMsg)

    await resumeChat(currentThreadId.value, resumeData, callbacks)
  }

  /** 构建 SSE 回调 */
  function _buildCallbacks(assistantMsg: ChatMessage): StreamCallbacks {
    function getNode(namespace: string[], agentName?: string): AgentNode {
      if (!assistantMsg.executionNodes) assistantMsg.executionNodes = []
      const id = namespaceKey(namespace) || 'main'
      let node = assistantMsg.executionNodes.find((item) => item.id === id)
      if (!node) {
        node = { id, namespace, agentName, content: '', toolCalls: [] }
        assistantMsg.executionNodes.push(node)
      } else if (!node.agentName && agentName) {
        node.agentName = agentName
      }
      return node
    }

    return {
      onConversation(threadId) {
        const isNew = !conversations.value.find((c) => c.key === threadId)
        currentThreadId.value = threadId
        if (isNew) {
          const firstUserMsg = messages.value.find((m) => m.role === 'user')
          const label = firstUserMsg
            ? firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '…' : '')
            : threadId.slice(0, 8)
          conversations.value.unshift({ key: threadId, label, timestamp: Date.now() })
        }
      },
      onChunk(chunk, namespace, meta) {
        assistantMsg.loading = false
        if (namespace.length === 0) {
          assistantMsg.content += chunk
          return
        }
        getNode(namespace, meta.lc_agent_name).content += chunk
      },
      onToolCallStart(calls) {
        assistantMsg.loading = false
        for (const tc of calls) {
          const node = getNode(tc.namespace, tc.agentName)
          const existing = node.toolCalls.find((tool) => tool.id === tc.id)
          if (existing) {
            existing.name = tc.name
            existing.args = tc.args
            continue
          }
          node.toolCalls.push({
            id: tc.id,
            name: tc.name,
            args: tc.args,
            status: 'running',
            startedAt: Date.now(),
            namespace: tc.namespace,
            agentName: tc.agentName,
            isDelegation: tc.name === 'task',
          })
        }
      },
      onToolResult(result) {
        const tool = assistantMsg.executionNodes
          ?.flatMap((node) => node.toolCalls)
          .find((item) => item.id === result.tool_call_id)
        if (tool) {
          tool.status = result.content.startsWith('Error') ? 'error' : 'success'
          tool.result = result.content
          tool.endedAt = Date.now()
          tool.isEvicted =
            result.content.includes('__evicted__') ||
            result.content.startsWith('file://') ||
            result.content.includes('agent_storage')
        }
      },
      onInterrupt(data) {
        assistantMsg.loading = false
        assistantMsg.interrupted = data
        pendingInterrupt.value = data
      },
      onDone() {
        assistantMsg.loading = false
        loading.value = false
        abortController.value = null
      },
      onError(err) {
        assistantMsg.loading = false
        assistantMsg.content = `请求失败：${err.message}`
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
