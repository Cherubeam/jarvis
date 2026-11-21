// Design tokens for the "Journal" look (2026-11). Documented in
// docs/design/tokens.md — keep the two in sync.
//
// The rules behind the values:
// - Neutral greys, no tinted surfaces. One accent; every other colour means
//   something (an error, an expensive turn, an added or removed line).
// - Two typefaces: `serif` for text you read, `mono` for text you typed and for
//   metadata (paths, times, counts, cost).
// - Every text colour keeps at least 4.5:1 contrast on the surfaces it sits on.

export type Theme = {
  user: string
  assistant: string
  tool: string
  error: string
  system: string
  stats: string
  cost: string
  costHigh: string
  add: string
  addBg: string
  del: string
  delBg: string
  surface0: string
  surface1: string
  surface2: string
  surface3: string
  border: string
  borderStrong: string
  textPrimary: string
  textSecondary: string
  textDisabled: string
  /** Font stack for the assistant's answers — serif by default, mono via Tweaks. */
  read: string
}

export const JARVIS_FONTS = {
  // No font files are bundled: the stack names faces that ship with macOS/iOS
  // after an optional locally installed Source Serif 4.
  serif: "'Source Serif 4', 'Iowan Old Style', Charter, Georgia, serif",
  mono: "'JetBrains Mono', 'JetBrainsMono Nerd Font', 'SF Mono', 'Fira Code', ui-monospace, Menlo, Consolas, monospace",
}

export const JARVIS_DARK: Theme = {
  user: '#A8A8A8',
  assistant: '#8FB0F8',
  tool: '#A8A8A8',
  error: '#F0908A',
  system: '#A8A8A8',
  stats: '#909090',
  cost: '#A8A8A8',
  costHigh: '#D9A94E',
  add: '#8FE0A5',
  addBg: '#1F3326',
  del: '#F0908A',
  delBg: '#3A2323',
  surface0: '#1E1E1E',
  surface1: '#232323',
  surface2: '#2A2A2A',
  surface3: '#363636',
  border: '#303030',
  borderStrong: '#4A4A4A',
  textPrimary: '#DCDCDC',
  textSecondary: '#A8A8A8',
  textDisabled: '#909090',
  read: JARVIS_FONTS.serif,
}

export const JARVIS_LIGHT: Theme = {
  user: '#5F5F5F',
  assistant: '#3557C9',
  tool: '#5F5F5F',
  error: '#B3261E',
  system: '#5F5F5F',
  stats: '#6E6E6E',
  cost: '#5F5F5F',
  costHigh: '#8A5A00',
  add: '#17662F',
  addBg: '#E6F4EA',
  del: '#A3261E',
  delBg: '#FBEAE8',
  surface0: '#FFFFFF',
  surface1: '#FAFAFA',
  surface2: '#F1F1F0',
  surface3: '#E4E4E2',
  border: '#E2E2E0',
  borderStrong: '#C9C9C6',
  textPrimary: '#1F1F1F',
  textSecondary: '#5F5F5F',
  textDisabled: '#6E6E6E',
  read: JARVIS_FONTS.serif,
}

export const JARVIS_SPACE = { 0: 0, 1: 4, 2: 8, 3: 12, 4: 16, 6: 24, 8: 32, 10: 40, 12: 48, 16: 64 }
export const JARVIS_RADIUS = { sm: 4, md: 4, lg: 6 }

/** Width of the reading column, and of the gutters either side of it (px). */
export const JARVIS_MEASURE = { gutter: 72, column: 640, gap: 28, page: 1000 }

export type AccentKey = 'blue' | 'steel' | 'teal' | 'amber' | 'rose'

export const ACCENT_HUES: Record<AccentKey, { dark: string; light: string }> = {
  blue:  { dark: '#8FB0F8', light: '#3557C9' },
  steel: { dark: '#7FB4CF', light: '#2F6F8F' },
  teal:  { dark: '#74DDD9', light: '#0B7A76' },
  amber: { dark: '#D9A94E', light: '#8A5A00' },
  rose:  { dark: '#E79AB8', light: '#A8325F' },
}
