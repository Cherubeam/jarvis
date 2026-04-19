// Design tokens — ported verbatim from JARVIS GUI.html lines 36-99.
// Keep in sync with the prototype; each colour is referenced in the prototype's
// docs/design/tokens.md.

export type Theme = {
  user: string
  assistant: string
  tool: string
  error: string
  system: string
  stats: string
  cost: string
  costHigh: string
  surface0: string
  surface1: string
  surface2: string
  surface3: string
  border: string
  borderStrong: string
  textPrimary: string
  textSecondary: string
  textDisabled: string
}

export const JARVIS_DARK: Theme = {
  user: '#4ADE80',
  assistant: '#22D3EE',
  tool: '#C084FC',
  error: '#F87171',
  system: '#FBBF24',
  stats: '#9CA3AF',
  cost: '#F59E0B',
  costHigh: '#EF4444',
  surface0: '#0B0F17',
  surface1: '#111827',
  surface2: '#1F2937',
  surface3: '#374151',
  border: '#1F2937',
  borderStrong: '#374151',
  textPrimary: '#F9FAFB',
  textSecondary: '#9CA3AF',
  textDisabled: '#4B5563',
}

export const JARVIS_LIGHT: Theme = {
  user: '#16A34A',
  assistant: '#0891B2',
  tool: '#9333EA',
  error: '#DC2626',
  system: '#D97706',
  stats: '#6B7280',
  cost: '#B45309',
  costHigh: '#DC2626',
  surface0: '#FFFFFF',
  surface1: '#FAFAF9',
  surface2: '#F3F4F6',
  surface3: '#E5E7EB',
  border: '#E5E7EB',
  borderStrong: '#D1D5DB',
  textPrimary: '#111827',
  textSecondary: '#6B7280',
  textDisabled: '#9CA3AF',
}

export const JARVIS_FONTS = {
  sans: "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  mono: "'JetBrains Mono', 'SF Mono', 'Fira Code', ui-monospace, Menlo, Consolas, monospace",
}

export const JARVIS_SPACE = { 0: 0, 1: 4, 2: 8, 3: 12, 4: 16, 6: 24, 8: 32, 10: 40, 12: 48, 16: 64 }
export const JARVIS_RADIUS = { sm: 4, md: 8, lg: 12 }

export type AccentKey = 'cyan' | 'violet' | 'amber' | 'rose' | 'emerald'

export const ACCENT_HUES: Record<AccentKey, { dark: string; light: string }> = {
  cyan:    { dark: '#22D3EE', light: '#0891B2' },
  violet:  { dark: '#A78BFA', light: '#7C3AED' },
  amber:   { dark: '#FBBF24', light: '#B45309' },
  rose:    { dark: '#FB7185', light: '#E11D48' },
  emerald: { dark: '#34D399', light: '#059669' },
}
