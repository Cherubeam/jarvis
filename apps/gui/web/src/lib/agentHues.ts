// Per-agent hue. The Journal look uses one accent for every agent: the name
// already says who it is, and fifteen pastel hues were decoration. The map and
// `hueFor` stay so a single agent can be given its own colour again here,
// without touching the components that call it.

export const AGENT_HUE_MAP: Record<string, string | null> = {}

export function hueFor(id: string | undefined, accent: string): string {
  if (!id) return accent
  const mapped = AGENT_HUE_MAP[id]
  return mapped ?? accent
}
