// Per-agent hue — stable across sidebar, list, detail, preview, filter chips.
// Ported verbatim from JARVIS GUI.html line 1425. Using oklch() lets the hue
// read correctly against both dark and light surfaces without a second map.

export const AGENT_HUE_MAP: Record<string, string | null> = {
  JARVIS: null, // use accent
  writer: 'oklch(0.78 0.12 145)',
  substack_publisher: 'oklch(0.78 0.12 125)',
  substack_image_creator: 'oklch(0.78 0.12 110)',
  researcher: 'oklch(0.78 0.12 55)',
  reading_assistant: 'oklch(0.78 0.12 70)',
  obsidian_note_creator: 'oklch(0.78 0.12 170)',
  pattern_language_expert: 'oklch(0.78 0.12 185)',
  navigator: 'oklch(0.78 0.12 220)',
  okr_architect: 'oklch(0.78 0.12 15)',
  tactics_coach: 'oklch(0.78 0.12 85)',
  content_reviewer: 'oklch(0.78 0.12 260)',
  strategyzer: 'oklch(0.78 0.12 280)',
  simplifier: 'oklch(0.78 0.12 45)',
  pattern_card_generator: 'oklch(0.78 0.12 330)',
  developer: 'oklch(0.78 0.12 300)',
}

export function hueFor(id: string | undefined, accent: string): string {
  if (!id) return accent
  const mapped = AGENT_HUE_MAP[id]
  return mapped ?? accent
}
