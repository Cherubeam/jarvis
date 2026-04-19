// Wire types — mirror apps/gui/server/protocol.py.

export type SessionMeta = {
  id: string
  model: string
  model_short: string
  provider: string
  conversation_path: string
  vault: string | null
  started_at: string
  agents_count: number
}

export type Stats = { tokens?: number; cost?: number; ttft?: number; total?: number }

export type DiffLine = { kind: 'add' | 'del' | 'ctx'; text: string }

export type RagMatch = { date: string; score: number; snippet: string; source: string }

export type ServerEvent =
  | { type: 'session_start'; session: SessionMeta }
  | { type: 'system'; text: string; time?: string }
  | { type: 'user'; id: string; text: string; time: string }
  | { type: 'thinking_start'; agent: string }
  | { type: 'thinking_end'; agent: string }
  | { type: 'chunk'; id: string; agent: string; delta: string }
  | { type: 'text'; id: string; agent: string; markdown: string; stats?: Stats }
  | {
      type: 'tool_call'
      id: string
      agent: string
      tool: string
      args: Record<string, unknown>
      result: { summary?: string; preview?: string; path?: string }
      elapsed_ms: number
      status: string
    }
  | { type: 'delegation'; id: string; from: string; to: string; reason: string }
  | {
      type: 'approval_pending'
      id: string
      tool: string
      agent: string
      path: string
      diff: DiffLine[]
      summary: string
    }
  | { type: 'approval_resolved'; id: string; approved: boolean }
  | { type: 'rag_result'; id: string; query: string; matches: RagMatch[] }
  | { type: 'error'; id?: string; message: string }
  | { type: 'totals'; messages: number; tokens: number; cost: number }
  | { type: 'turn_finished'; id: string }

export type ClientMsg =
  | { type: 'submit'; text: string }
  | { type: 'approval_decision'; id: string; approved: boolean }
  | { type: 'cancel' }

export type Agent = {
  name: string
  command: string
  description: string
  tools: string[]
}
