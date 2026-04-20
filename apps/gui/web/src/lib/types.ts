// Wire types — mirror apps/gui/server/protocol.py.

export type SessionMeta = {
  id: string              // internal conversation_id (conv_YYYYMMDD_HHMMSS_hex)
  file_id: string         // filename stem matching ConversationSummary.id
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

// -- Conversations (Phase 2) ------------------------------------------------

export type ConversationSummary = {
  id: string              // filename stem e.g. "2026-04-19_15-02-17"
  date: string            // "YYYY-MM-DD"
  title: string
  agents: string[]        // dominant first
  messages: number
  tokens: number
  cost: number
  duration_ms: number
  tool_calls: number
  tools: string[]
  handoffs: number
  model: string
  provider: string
}

export type PreviewMessage = { role: string; text: string }

export type ConversationDetail = ConversationSummary & {
  messages: Record<string, unknown>[]
  preview: PreviewMessage[]
}

export type ConversationListResponse = {
  items: ConversationSummary[]
  total: number
  limit: number
  offset: number
}

export type FacetEntry = { id: string; count: number }

export type HistoryFacets = {
  agents: FacetEntry[]
  tools: FacetEntry[]
  total: number
}

export type DatePreset = 'all' | 'today' | '7d' | '30d'
export type SortMode = 'recent' | 'cost' | 'messages'

// -- Home / Dashboard (Phase 3) ---------------------------------------------

export type HomeTask = {
  title: string
  project: string | null
  when_date: string | null
  priority: 'high' | 'medium' | 'low'
  list: 'today' | 'upcoming' | 'inbox'
  linked_conversation_ids: string[]
}

export type CostWeekDay = {
  date: string
  cost: number
  conversations: number
}

export type QuickStartEntry = {
  label: string
  cmd: string | null
  agent: string
}

export type HomeData = {
  greeting: string
  today: { date: string; day_label: string }
  tasks: HomeTask[]
  cost_week: {
    days: CostWeekDay[]
    total: number
    conversation_count: number
  }
  resume: ConversationSummary | null
  recent: ConversationSummary[]
  quick_start: QuickStartEntry[]
}
