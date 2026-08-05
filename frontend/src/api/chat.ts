import type {
  AgentNode,
  DecisionType,
  InterruptAction,
  InterruptData,
  MessageMeta,
  Namespace,
  ResumePayload,
} from '@/types/agent'

/**
 * Temporary development JWT. A real login flow must set VITE_DEV_JWT with a
 * signed token; the backend currently reads `sub` and `username` claims.
 */
const DEVELOPMENT_JWT =
  'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJkZW1vLXVzZXIiLCJ1c2VybmFtZSI6IkRlbW8gVXNlciJ9.'

function authHeaders(): HeadersInit {
  return {
    Authorization: `Bearer ${import.meta.env.VITE_DEV_JWT || DEVELOPMENT_JWT}`,
  }
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  executionNodes?: AgentNode[]
  interrupted?: InterruptData
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
 * GET /api/history
 * 后端返回 { threads: ThreadInfo[] }
 */
export async function fetchHistory(): Promise<ConversationItem[]> {
  try {
    const res = await fetch('/api/history', { headers: authHeaders() })
    if (!res.ok) return []
    const data: { threads: ThreadInfo[] } = await res.json()
    const threads = data.threads ?? []
    return threads.map((t) => ({
      key: t.thread_id,
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
 * GET /api/chat/{thread_id}/messages
 * 返回指定会话的历史消息列表
 */
export async function fetchThreadMessages(threadId: string): Promise<ChatMessage[]> {
  try {
    const res = await fetch(`/api/chat/${encodeURIComponent(threadId)}/messages`, {
      headers: authHeaders(),
    })
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
 * POST /api/chat/{thread_id}/resume
 *
 * HITL 恢复。`resume` 直接传给 `Command(resume=...)`，因此必须是
 * HumanInTheLoopMiddleware 期望的 `{ decisions: [...] }` 结构 —— 每个待审
 * 操作对应一个 decision，顺序与 interrupt 的 actions 一致。
 */
export async function resumeChat(
  threadId: string,
  resumeData: ResumePayload,
  callbacks: StreamCallbacks,
): Promise<void> {
  try {
    const res = await fetch(`/api/chat/${encodeURIComponent(threadId)}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ resume: resumeData }),
      signal: callbacks.signal,
    })
    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`)
    }
    await _consumeSseStream(res.body, callbacks)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return
    callbacks.onError(err instanceof Error ? err : new Error(String(err)))
  }
}

// ────────────────────────────────────────────────────────────────
// streamChat — SSE 流式对话
// ────────────────────────────────────────────────────────────────

/** 一次工具调用的开始事件，带上发起它的 agent 身份 */
export interface ToolCallStart {
  id: string
  name: string
  args: Record<string, unknown>
  namespace: Namespace
  agentName?: string
}

export interface StreamCallbacks {
  onConversation: (threadId: string) => void
  /** AI 文本增量；namespace 用于区分主 agent 与子 agent 的输出 */
  onChunk: (chunk: string, namespace: Namespace, meta: MessageMeta) => void
  /** AI 决定调用工具 */
  onToolCallStart: (calls: ToolCallStart[]) => void
  /** 工具执行完毕，返回结果 */
  onToolResult: (result: {
    tool_call_id: string
    content: string
    namespace: Namespace
  }) => void
  onInterrupt: (data: InterruptData) => void
  onDone: () => void
  onError: (err: Error) => void
  /** 外部 AbortController.signal，用于取消流 */
  signal?: AbortSignal
}

export async function streamChat(
  message: string,
  threadId: string | null,
  callbacks: StreamCallbacks,
): Promise<void> {
  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        message,
        ...(threadId ? { thread_id: threadId } : {}),
      }),
      signal: callbacks.signal,
    })

    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`)
    }

    await _consumeSseStream(res.body, callbacks)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return
    callbacks.onError(err instanceof Error ? err : new Error(String(err)))
  }
}

// ────────────────────────────────────────────────────────────────
// 内部：SSE 流消费 + 事件派发
// ────────────────────────────────────────────────────────────────

/**
 * 消费 SSE 流。
 *
 * sse-starlette 用 `\r\n` 作为行分隔符，因此按 `\r?\n` 切分；`data:` 后的
 * 空格按规范是可选的。终止事件（complete / error）由服务端显式发送；若连接
 * 直接断开，则在 reader 结束时兜底调用 onDone。
 */
async function _consumeSseStream(
  body: ReadableStream<Uint8Array>,
  callbacks: StreamCallbacks,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''
  let dataLines: string[] = []
  let terminated = false

  const flush = (): boolean => {
    if (dataLines.length === 0) {
      currentEvent = ''
      return false
    }
    const raw = dataLines.join('\n')
    dataLines = []
    const event = currentEvent
    currentEvent = ''
    if (!raw || raw === '[DONE]') return false
    try {
      _dispatchEvent(event, JSON.parse(raw), callbacks)
    } catch {
      return false // 忽略非 JSON 行
    }
    return event === 'complete' || event === 'error'
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (line === '') {
          if (flush()) {
            terminated = true
            return
          }
          continue
        }
        if (line.startsWith(':')) continue // 注释 / 心跳
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
          continue
        }
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).replace(/^ /, ''))
        }
      }
    }
    // 连接结束前可能还有未以空行收尾的事件
    if (flush()) terminated = true
  } finally {
    reader.releaseLock()
    // 服务端已发过 complete / error 时不要重复收尾，否则会覆盖错误状态
    if (!terminated) callbacks.onDone()
  }
}

function _namespaceOf(parsed: Record<string, unknown>): Namespace {
  const ns = parsed.namespace
  return Array.isArray(ns) ? (ns as Namespace) : []
}

function _metaOf(parsed: Record<string, unknown>): MessageMeta {
  const meta = parsed.meta
  return meta && typeof meta === 'object' ? (meta as MessageMeta) : {}
}

function _dispatchEvent(
  event: string,
  parsed: Record<string, unknown>,
  cbs: Omit<StreamCallbacks, 'signal'>,
): void {
  const { onConversation, onChunk, onToolCallStart, onToolResult, onInterrupt, onDone, onError } =
    cbs

  switch (event) {
    case 'conversation':
      if (parsed.thread_id) onConversation(parsed.thread_id as string)
      break

    case 'message_chunk': {
      const namespace = _namespaceOf(parsed)
      const meta = _metaOf(parsed)
      const agentName = meta.lc_agent_name
      const msgType = parsed.type as string | undefined

      // 情况 1：AI 文本内容流。仅接受 ai 消息，避免把 ToolMessage 的
      // content 当成助手文本追加到气泡里。
      if (msgType === 'ai' || msgType === 'AIMessageChunk') {
        const content = parsed.content
        if (typeof content === 'string' && content) {
          onChunk(content, namespace, meta)
        } else if (Array.isArray(content)) {
          for (const block of content) {
            if (block?.type === 'text' && block.text) {
              onChunk(block.text as string, namespace, meta)
            }
          }
        }
      }

      // 情况 2：AI 决定调用工具（tool_calls 非空）
      const toolCalls = parsed.tool_calls
      if (Array.isArray(toolCalls) && toolCalls.length > 0) {
        onToolCallStart(
          toolCalls.map((tc: Record<string, unknown>) => ({
            id: (tc.id ?? '') as string,
            name: (tc.name ?? '') as string,
            args: (tc.args ?? {}) as Record<string, unknown>,
            namespace,
            agentName,
          })),
        )
      }

      // 情况 3：工具执行结果（ToolMessage 带 tool_call_id）
      if (parsed.tool_call_id) {
        onToolResult({
          tool_call_id: parsed.tool_call_id as string,
          content:
            typeof parsed.content === 'string'
              ? parsed.content
              : JSON.stringify(parsed.content ?? ''),
          namespace,
        })
      }
      break
    }

    case 'interrupt': {
      const actions = Array.isArray(parsed.actions)
        ? (parsed.actions as InterruptAction[])
        : []
      const allowed = Array.isArray(parsed.allowed_decisions)
        ? (parsed.allowed_decisions as DecisionType[])
        : []
      onInterrupt({
        thread_id: (parsed.thread_id ?? '') as string,
        interrupt_id: parsed.interrupt_id as string | undefined,
        namespace: _namespaceOf(parsed),
        interrupt_mode: parsed.interrupt_mode === 'input' ? 'input' : 'approval',
        allowed_decisions: allowed,
        actions,
        hint: (parsed.hint ?? '') as string,
        value: parsed.value,
      })
      break
    }

    case 'complete':
      onDone()
      break

    case 'error':
      onError(new Error((parsed.message as string) ?? 'Unknown server error'))
      break

    // graph_state — 暂不处理
  }
}
