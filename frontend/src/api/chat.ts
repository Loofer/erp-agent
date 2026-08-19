import type {
  DecisionType,
  InterruptAction,
  InterruptData,
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
  kind: 'user' | 'assistant' | 'agent_routing' | 'tool_call' | 'tool_result'
  role?: 'user' | 'assistant'
  content: string
  actorName?: string
  toolCallId?: string
  toolName?: string
  toolArgs?: Record<string, unknown>
  targetAgent?: string
  description?: string
  namespace?: string[]
  eventData?: Record<string, unknown>
  status?: 'running' | 'success' | 'error'
  loading?: boolean
  interrupted?: InterruptData
}

/** 后端 SessionInfo 结构；thread_id 是 LangGraph 的唯一会话标识。 */
export interface SessionInfo {
  thread_id: string
  user_id: string
  agent_id: string
  created_at: string | null
  updated_at: string | null
  initial_prompt: string | null
  message_count: number
}

export interface SessionItem {
  key: string
  label: string
  timestamp?: number
}

/**
 * GET /api/history
 * 后端返回 { sessions: SessionInfo[] }
 */
export async function fetchSessions(): Promise<SessionItem[]> {
  try {
    const res = await fetch('/api/history', { headers: authHeaders() })
    if (!res.ok) return []
    const data: { sessions: SessionInfo[] } = await res.json()
    const sessions = data.sessions ?? []
    return sessions.map((t) => ({
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
export async function fetchSessionMessages(threadId: string): Promise<ChatMessage[]> {
  try {
    const res = await fetch(`/api/chat/${encodeURIComponent(threadId)}/messages`, {
      headers: authHeaders(),
    })
    if (!res.ok) return []
    const data: { messages: Array<Record<string, unknown>> } = await res.json()
    return (data.messages ?? []).map((m) => ({
      id: typeof m.id === 'string' && m.id ? m.id : crypto.randomUUID(),
      kind: ['agent_routing', 'tool_call', 'tool_result', 'user'].includes(String(m.kind))
        ? (m.kind as ChatMessage['kind'])
        : 'assistant',
      role: m.role === 'user' ? 'user' : m.role === 'assistant' ? 'assistant' : undefined,
      content: typeof m.content === 'string' ? m.content : '',
      actorName: typeof m.actor_name === 'string' ? m.actor_name : undefined,
      toolCallId: typeof m.tool_call_id === 'string' ? m.tool_call_id : undefined,
      toolName: typeof m.tool_name === 'string' ? m.tool_name : undefined,
      toolArgs:
        m.tool_args && typeof m.tool_args === 'object'
          ? (m.tool_args as Record<string, unknown>)
          : undefined,
      targetAgent: typeof m.subagent_type === 'string' ? m.subagent_type : undefined,
      description: typeof m.description === 'string' ? m.description : undefined,
      namespace: Array.isArray(m.namespace)
        ? m.namespace.filter((value): value is string => typeof value === 'string')
        : undefined,
      status:
        m.status === 'running' || m.status === 'success' || m.status === 'error'
          ? m.status
          : undefined,
    }))
  } catch {
    return []
  }
}

/** DELETE /api/chat/{thread_id}，删除会话及其所有 Agent checkpoint。 */
export async function deleteSession(threadId: string): Promise<void> {
  const res = await fetch(`/api/chat/${encodeURIComponent(threadId)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  }
}

/**
 * POST /api/chat/{thread_id}/resume
 *
 * HITL 恢复。`resume` 直接传给 `Command(resume=...)`：审批中断使用
 * `{ decisions: [...] }`，工具内原生输入中断使用用户输入字符串。
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
  agentName?: string
  namespace?: string[]
  eventData?: Record<string, unknown>
}

export interface StreamCallbacks {
  onSession: (threadId: string) => void
  /** AI 文本增量；namespace 用于区分主 agent 与子 agent 的输出 */
  onChunk: (
    chunk: string,
    messageId: string,
    agentName?: string,
    namespace?: string[],
  ) => void
  /** AI 决定调用工具 */
  onToolCallStart: (calls: ToolCallStart[]) => void
  onAgentRouting: (routing: {
    id: string
    toolCallId: string
    agentName?: string
    targetAgent?: string
    description?: string
    namespace?: string[]
    eventData?: Record<string, unknown>
  }) => void
  /** 工具执行完毕，返回结果 */
  onToolResult: (result: {
    id: string
    tool_call_id: string
    content: string
    toolName?: string
    isError: boolean
    agentName?: string
    namespace?: string[]
    eventData?: Record<string, unknown>
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

function _string(value: unknown): string | undefined {
  return typeof value === 'string' && value ? value : undefined
}

function _namespaceOf(parsed: Record<string, unknown>): string[] | undefined {
  return Array.isArray(parsed.namespace)
    ? parsed.namespace.filter((value): value is string => typeof value === 'string')
    : undefined
}

function _eventData(parsed: Record<string, unknown>): Record<string, unknown> {
  return parsed.data && typeof parsed.data === 'object'
    ? (parsed.data as Record<string, unknown>)
    : {}
}

function _dispatchEvent(
  event: string,
  parsed: Record<string, unknown>,
  cbs: Omit<StreamCallbacks, 'signal'>,
): void {
  const { onSession, onChunk, onToolCallStart, onAgentRouting, onToolResult, onInterrupt, onDone, onError } = cbs
  const data = _eventData(parsed)
  const agentName = _string(parsed.agent_name)
  const namespace = _namespaceOf(parsed)
  const messageId = _string(parsed.message_id)

  switch (event) {
    case 'session':
      if (parsed.thread_id) onSession(parsed.thread_id as string)
      break

    case 'message_chunk': {
      const content = _string(data.content)
      if (content) {
        onChunk(content, messageId ?? crypto.randomUUID(), agentName, namespace)
      }
      break
    }

    case 'agent_routing':
      onAgentRouting({
        id: _string(parsed.event_id) ?? crypto.randomUUID(),
        toolCallId: _string(data.tool_call_id) ?? '',
        agentName,
        targetAgent: _string(data.subagent_type),
        description: _string(data.description),
        namespace,
        eventData: parsed,
      })
      break

    case 'tool_call_start':
      onToolCallStart([{
        id: _string(data.tool_call_id) ?? '',
        name: _string(data.tool_name) ?? 'tool',
        args: data.args && typeof data.args === 'object'
          ? (data.args as Record<string, unknown>) : {},
        agentName,
        namespace,
        eventData: parsed,
      }])
      break

    case 'tool_call_end':
      onToolResult({
        id: messageId ?? _string(parsed.event_id) ?? crypto.randomUUID(),
        tool_call_id: _string(data.tool_call_id) ?? '',
        content: typeof data.result === 'string' ? data.result : JSON.stringify(data.result ?? ''),
        toolName: _string(data.tool_name),
        isError: data.tool_status === 'error',
        agentName,
        namespace,
        eventData: parsed,
      })
      break

    case 'interrupt': {
      const actions = Array.isArray(data.actions)
        ? (data.actions as InterruptAction[])
        : []
      const allowed = Array.isArray(data.allowed_decisions)
        ? (data.allowed_decisions as DecisionType[])
        : []
      onInterrupt({
        thread_id: _string(parsed.thread_id) ?? '',
        interrupt_id: _string(data.interrupt_id),
        namespace: namespace ?? [],
        interrupt_mode: data.interrupt_mode === 'input' ? 'input' : 'approval',
        resume_mode: data.resume_mode === 'value' ? 'value' : 'decisions',
        allowed_decisions: allowed,
        actions,
        hint: _string(data.hint) ?? '',
        value: data.value,
      })
      break
    }

    case 'complete':
      onDone()
      break

    case 'error':
      onError(new Error(_string(data.message) ?? 'Unknown server error'))
      break

    // graph_state — 暂不处理
  }
}
