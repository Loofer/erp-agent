/** 硬编码用户 ID，后续接入登录后替换 */
export const CURRENT_USER_ID = 'demo-user'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
}

/** 后端 ThreadInfo 结构 */
export interface ThreadInfo {
  thread_id: string
  user_id: string
  agent_id: string
  created_at: string | null
  updated_at: string | null
  initial_prompt: string | null
  message_count: number
}

export interface ConversationItem {
  key: string
  label: string
  timestamp?: number
}

/**
 * GET /api/history?user_id=<id>
 * 后端返回 { threads: ThreadInfo[] }
 */
export async function fetchHistory(): Promise<ConversationItem[]> {
  try {
    const res = await fetch(`/api/history?user_id=${CURRENT_USER_ID}`)
    if (!res.ok) return []
    const data: { threads: ThreadInfo[] } = await res.json()
    const threads = data.threads ?? []
    return threads.map((t) => ({
      key: t.thread_id,
      // 优先用首条消息摘要，截断到 30 字
      label: t.initial_prompt
        ? t.initial_prompt.slice(0, 30) + (t.initial_prompt.length > 30 ? '…' : '')
        : t.thread_id.slice(0, 8),
      timestamp: t.updated_at ? new Date(t.updated_at).getTime() : undefined,
    }))
  } catch {
    return []
  }
}

/**
 * GET /api/chat/{thread_id}/messages?user_id=<id>
 * 返回指定会话的历史消息列表
 */
export async function fetchThreadMessages(threadId: string): Promise<ChatMessage[]> {
  try {
    const res = await fetch(
      `/api/chat/${encodeURIComponent(threadId)}/messages?user_id=${CURRENT_USER_ID}`,
    )
    if (!res.ok) return []
    const data: { messages: Array<{ id: string; role: string; content: string }> } =
      await res.json()
    return (data.messages ?? []).map((m) => ({
      id: m.id || crypto.randomUUID(),
      role: m.role === 'user' ? 'user' : 'assistant',
      content: m.content,
    }))
  } catch {
    return []
  }
}

/**
 * POST /api/chat/stream — SSE 流式对话
 *
 * SSE 事件类型：
 *   conversation   → { thread_id }         首个事件，携带 thread_id
 *   message_chunk  → { content, ... }      内容片段，content 可为 string | ContentBlock[]
 *   complete       → { thread_id }         流结束
 *   error          → { error }             错误
 *   interrupt      → { thread_id, ... }    HITL 中断（暂忽略）
 */
export async function streamChat(
  message: string,
  threadId: string | null,
  callbacks: {
    onConversation: (threadId: string) => void
    onChunk: (chunk: string) => void
    onDone: () => void
    onError: (err: Error) => void
  },
): Promise<void> {
  const { onConversation, onChunk, onDone, onError } = callbacks

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        user_id: CURRENT_USER_ID,
        ...(threadId ? { thread_id: threadId } : {}),
      }),
    })

    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        onDone()
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        // 空行 = SSE 消息边界，重置事件类型
        if (line.trim() === '') {
          currentEvent = ''
          continue
        }

        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
          continue
        }

        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw || raw === '[DONE]') continue

        try {
          const parsed = JSON.parse(raw)

          switch (currentEvent) {
            case 'conversation':
              if (parsed.thread_id) onConversation(parsed.thread_id)
              break

            case 'message_chunk': {
              // LangGraph message 的 content 可以是 string 或 ContentBlock[]
              const content = parsed.content
              if (typeof content === 'string' && content) {
                onChunk(content)
              } else if (Array.isArray(content)) {
                for (const block of content) {
                  if (block?.type === 'text' && block.text) onChunk(block.text)
                }
              }
              break
            }

            case 'complete':
              onDone()
              return

            case 'error':
              onError(new Error(parsed.error ?? 'Unknown server error'))
              return

            // interrupt / graph_state / node_start / node_end — 暂忽略
          }
        } catch {
          // 忽略非 JSON 行
        }
      }
    }
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)))
  }
}
