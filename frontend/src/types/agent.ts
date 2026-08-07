/**
 * Agent tool call and HITL interrupt types.
 * Shared by the SSE parser, Pinia store, and all UI components.
 */

/**
 * Namespace identifying which (sub)agent emitted an event.
 * `[]` is the main agent; a non-empty path means a subagent, e.g.
 * `["tools:8eb96549-1e5a-e6e4-e698-1bd742a27973"]`.
 */
export type Namespace = string[]

/** Per-message metadata the backend forwards from LangGraph. */
export interface MessageMeta {
  /** Graph node that produced the message, e.g. "model" or "tools" */
  langgraph_node?: string
  langgraph_step?: number
  /** Subagent name, e.g. "supplier_manager". Absent on the main agent. */
  lc_agent_name?: string
  checkpoint_ns?: string
}

/** Stable key for a namespace; `''` is the main agent. */
export function namespaceKey(ns: Namespace | undefined): string {
  return (ns ?? []).join('|')
}

export interface ToolCall {
  /** LangChain tool_call id, e.g. "call_ba1e5ca45b884ed6ab9321" */
  id: string
  /** Tool function name, e.g. "get_dashboard" */
  name: string
  /** Arguments passed to the tool */
  args: Record<string, unknown>
  status: 'pending' | 'running' | 'success' | 'error'
  /** Raw string content returned by the tool */
  result?: string
  /**
   * True when FilesystemMiddleware evicted the result to disk because it
   * exceeded tool_token_limit_before_evict. The result field will contain
   * the short eviction reference instead of the full payload.
   */
  isEvicted?: boolean
  /** Date.now() when the tool started executing */
  startedAt?: number
  /** Date.now() when the tool finished */
  endedAt?: number
  /** Namespace of the agent that invoked this tool */
  namespace: Namespace
  /**
   * Subagent that invoked this tool, from meta.lc_agent_name.
   * Undefined for the main agent.
   */
  agentName?: string
  /**
   * True for the deep-agents `task` tool, which delegates to a subagent.
   * Its child tool calls arrive under a deeper namespace.
   */
  isDelegation?: boolean
}

/**
 * One graph invocation shown in the optional execution panel. The main
 * agent's user-facing text is deliberately not stored here; subagent text is
 * isolated here so it can never be appended to the final answer.
 */
export interface AgentNode {
  /** namespaceKey() of the emitting graph invocation */
  id: string
  namespace: Namespace
  /** Subagent name, or undefined for the main agent */
  agentName?: string
  /** Internal subagent output. Empty for the main agent node. */
  content: string
  toolCalls: ToolCall[]
}

/**
 * HITL interrupt mode:
 *   "approval" — user picks one of `allowed_decisions`; text input disabled.
 *   "input"    — the only allowed decision is "respond", so the user must type
 *                a message that stands in for the tool result.
 *
 * The backend derives the mode from the interrupt's `review_configs`, so it
 * always matches what HumanInTheLoopMiddleware accepts on resume.
 */
export type InterruptMode = 'approval' | 'input'

/** Shape expected by Command(resume=...) for this interrupt. */
export type InterruptResumeMode = 'decisions' | 'value'

/** Decisions HumanInTheLoopMiddleware accepts. */
export type DecisionType = 'approve' | 'edit' | 'reject' | 'respond'

/** One tool call awaiting human review. */
export interface InterruptAction {
  name: string
  args: Record<string, unknown>
  description: string
  allowed_decisions: DecisionType[]
}

export interface InterruptData {
  thread_id: string
  /** LangGraph Interrupt.id — deduplicates re-emission while unwinding */
  interrupt_id?: string
  /** Namespace of the agent that raised the interrupt */
  namespace: Namespace
  interrupt_mode: InterruptMode
  resume_mode: InterruptResumeMode
  /** Union of allowed decisions across all pending actions */
  allowed_decisions: DecisionType[]
  /** Tool calls awaiting review */
  actions: InterruptAction[]
  /** Human-readable hint; doubles as Sender placeholder for input-mode HITL */
  hint: string
  /** Raw interrupt value, for non-HITL interrupts and debugging */
  value?: unknown
}

/**
 * Resume payload expected by HumanInTheLoopMiddleware:
 * `Command(resume={"decisions": [...]})`, one decision per pending action.
 */
export type Decision =
  | { type: 'approve' }
  | { type: 'reject'; message?: string }
  | { type: 'edit'; edited_action: { name: string; args: Record<string, unknown> } }
  | { type: 'respond'; message: string }

export interface DecisionResumePayload {
  decisions: Decision[]
}

export type ResumePayload = DecisionResumePayload | string
