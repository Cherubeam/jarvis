import type { ReactNode } from 'react'

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

export function Row({
  theme,
  accent,
  label,
  labelColor,
  mono,
  dense,
  children,
}: {
  theme: Theme
  accent?: string
  label: string
  labelColor?: string
  mono?: boolean
  dense?: boolean
  children: ReactNode
}) {
  return (
    <div
      style={{
        padding: dense ? '10px 24px' : '14px 28px',
        borderLeft: `2px solid ${accent || 'transparent'}`,
        display: 'grid',
        gridTemplateColumns: '96px 1fr',
        gap: 16,
        alignItems: 'baseline',
      }}
    >
      <div
        style={{
          fontFamily: mono ? JARVIS_FONTS.mono : JARVIS_FONTS.sans,
          fontSize: 12,
          color: labelColor || theme.textSecondary,
          fontWeight: 700,
          letterSpacing: 0.3,
          paddingTop: 2,
        }}
      >
        {label}
      </div>
      <div style={{ color: theme.textPrimary, fontSize: 15, lineHeight: 1.65, minWidth: 0 }}>
        {children}
      </div>
    </div>
  )
}
