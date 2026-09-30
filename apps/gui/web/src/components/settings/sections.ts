// Section registry — one entry per top-level Settings section, except `gui`
// (restart-only origin allowlist, edited in config/local.yaml; see GuiSettings).
// The order here drives the left nav.

export type SectionKey =
  | 'models'
  | 'paths'
  | 'cli'
  | 'outcomes'
  | 'things3'
  | 'evaluation'
  | 'rag'
  | 'routing'
  | 'summarization'
  | 'obsidian'
  | 'mcp'
  | 'filesystem'
  | 'readwise'
  | 'pattern_cards'

export type Section = { key: SectionKey; label: string }

export const SECTIONS: Section[] = [
  { key: 'models', label: 'Models' },
  { key: 'paths', label: 'Paths' },
  { key: 'cli', label: 'CLI' },
  { key: 'outcomes', label: 'Outcomes' },
  { key: 'things3', label: 'Things 3' },
  { key: 'evaluation', label: 'Evaluation' },
  { key: 'rag', label: 'RAG' },
  { key: 'routing', label: 'Routing' },
  { key: 'summarization', label: 'Summarization' },
  { key: 'obsidian', label: 'Obsidian' },
  { key: 'mcp', label: 'MCP' },
  { key: 'filesystem', label: 'Filesystem' },
  { key: 'readwise', label: 'Readwise' },
  { key: 'pattern_cards', label: 'Pattern Cards' },
]
