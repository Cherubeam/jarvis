// Category grouping for the Agents overview grid.
// Ported verbatim from JARVIS GUI v6 line 1414. Any agent id whose name
// doesn't appear below lands under the synthetic `other` bucket so newly
// added agents are visible (rather than silently hidden).

export type AgentCategory = {
  id: string
  label: string
  members: string[]
}

export const AGENT_CATEGORIES: AgentCategory[] = [
  { id: 'writing',    label: 'Writing',     members: ['writer', 'substack_publisher', 'substack_image_creator'] },
  { id: 'knowledge',  label: 'Knowledge',   members: ['researcher', 'reading_assistant', 'obsidian_note_creator', 'pattern_language_expert'] },
  { id: 'planning',   label: 'Planning',    members: ['navigator', 'okr_architect', 'tactics_coach'] },
  { id: 'analysis',   label: 'Analysis',    members: ['content_reviewer', 'strategyzer', 'simplifier'] },
  { id: 'generation', label: 'Generation',  members: ['pattern_card_generator'] },
  { id: 'dev',        label: 'Engineering', members: ['developer'] },
]

/** Group agent ids into category buckets; unknown ids fall into `other`. */
export function groupByCategory(agentIds: string[]): AgentCategory[] {
  const known = new Set(AGENT_CATEGORIES.flatMap((c) => c.members))
  const other = agentIds.filter((id) => id !== 'JARVIS' && !known.has(id))
  const groups = AGENT_CATEGORIES.map((cat) => ({
    ...cat,
    members: cat.members.filter((m) => agentIds.includes(m)),
  })).filter((cat) => cat.members.length > 0)
  if (other.length > 0) {
    groups.push({ id: 'other', label: 'Other', members: other })
  }
  return groups
}
