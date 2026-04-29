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
  | { type: 'resume'; file_id: string }

export type Agent = {
  name: string
  command: string
  description: string
  tools: string[]
}

export type AgentDetail = {
  name: string
  command: string
  description: string
  tools: string[]
  temperature: number | null
  max_tokens: number | null
  max_iterations: number | null
  skills: string[]
  prompt_path: string | null      // null for JARVIS (prompt is assembled dynamically)
  prompt_includes_count: number
  model: string | null
  last_used: string | null
  recent_sessions: ConversationSummary[]
  cost_14d: { date: string; cost: number }[]
  cost_14d_total: number
}

// -- Agent prompt editor (Phase 6) ------------------------------------------

export type PromptResponse = {
  content: string
  path: string | null              // null for JARVIS
  bytes: number
  last_modified_iso: string | null
  editable: boolean
  explanation: string | null       // present for JARVIS read-only notice
}

export type PromptSnapshotKind = 'save' | 'pre_first_save' | 'pre_restore'

export type PromptSnapshot = {
  id: string
  timestamp: string
  bytes: number
  kind: PromptSnapshotKind
  note?: string
}

export type PromptSnapshotDetail = PromptSnapshot & { content: string }

export type PromptSaveResult = {
  bytes: number
  last_modified_iso: string
  snapshot_id: string
}

export type PromptIncludeRow = {
  placeholder: string
  filename: string
  status:
    | 'found_local'
    | 'found_shared'
    | 'found_local_example'
    | 'found_shared_example'
    | 'missing'
  path: string | null
}

export type PromptStats = {
  char_count: number
  line_count: number
  token_estimate: number
  token_estimate_method: string
  last_modified_iso: string | null
  snapshot_count: number
  prompt_includes: PromptIncludeRow[]
}

export type PromptResolved = { resolved_content: string }

// -- Prompt-include editor (Phase 6 follow-up) ------------------------------

export type IncludeStatus =
  | 'found_local'
  | 'found_shared'
  | 'found_local_example'
  | 'found_shared_example'
  | 'missing'

export type IncludeRow = {
  placeholder: string
  filename: string
  status: IncludeStatus
  path: string | null
  bytes: number | null
  last_modified_iso: string | null
  editable: boolean
  affects_agents: string[]
}

export type IncludeDetail = IncludeRow & { content: string }

export type IncludeSaveResult = {
  bytes: number
  last_modified_iso: string
  snapshot_id: string
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

// -- Outcomes (Phase 7) -----------------------------------------------------

export type OutcomeVerdict = 'happened' | 'didnt' | 'partial'

export type PendingOutcome = {
  file_id: string
  what: string | null
  why: string | null
  created_at: string | null
  revisit_at: string
  success_looks_like: string | null
}

export type ReviewOutcomeResult = {
  file_id: string
  reviewed_at: string
  outcome: OutcomeVerdict
  quality: number
}

// -- Settings (Phase 8 / PR-8b) ---------------------------------------------

export type SettingsResponse = {
  settings: Record<string, unknown>
  defaults: Record<string, unknown>
  overrides: Record<string, unknown>
  local_yaml_has_managed_header: boolean
  paths: { default_yaml: string; local_yaml: string }
}

export type PutSettingsResult = {
  overrides: Record<string, unknown>
  bytes: number
  restart_required: boolean
  hot_applied_fields: string[]
  restart_required_fields: string[]
}

export type SettingsValidationError = {
  loc: Array<string | number>
  card_loc: Array<string | number>
  msg: string
  type: string
  kind: 'field' | 'model_validator'
}

export type JsonSchemaNode = Record<string, unknown>
