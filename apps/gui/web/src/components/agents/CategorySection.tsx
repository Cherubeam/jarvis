// Category section header + 3-column grid wrapper for AgentCards.
// Ported from JARVIS GUI v6 line 1830.

import type { ReactNode } from 'react'

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

export function CategorySection({
  theme,
  label,
  children,
  featured = false,
}: {
  theme: Theme
  label: string
  children: ReactNode
  featured?: boolean
}) {
  return (
    <div style={{ marginBottom: featured ? 28 : 24 }}>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 10,
          letterSpacing: 1.4,
          color: theme.textDisabled,
          textTransform: 'uppercase',
          marginBottom: 10,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span>{label}</span>
        <span style={{ flex: 1, height: 1, background: theme.border }} />
      </div>
      {featured ? (
        children
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          {children}
        </div>
      )}
    </div>
  )
}
