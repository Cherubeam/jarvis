// Capitalization rule #3: speakers Title Case, system affordances lowercase.
// Acronym-aware. Ported from JARVIS GUI.html line 497-514.

const ACRONYMS = new Set([
  'okr', 'mcp', 'rag', 'api', 'cli', 'gui', 'llm', 'ttft', 'url', 'json', 'yaml', 'pdf', 'id',
])

export function speakerLabel(agentId: string): string {
  if (!agentId) return ''
  if (agentId === 'JARVIS' || agentId === 'You') return agentId
  return agentId
    .split('_')
    .map((part) => {
      if (ACRONYMS.has(part.toLowerCase())) return part.toUpperCase()
      return part.charAt(0).toUpperCase() + part.slice(1)
    })
    .join(' ')
}
