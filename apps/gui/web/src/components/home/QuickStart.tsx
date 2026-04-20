import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { QuickStartEntry } from '../../lib/types'

export function QuickStart({
  theme,
  accent,
  items,
  onStartChat,
}: {
  theme: Theme
  accent: string
  items: QuickStartEntry[]
  onStartChat: (cmd: string | null) => void
}) {
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {items.map((q, i) => (
        <button
          key={i}
          onClick={() => onStartChat(q.cmd ? q.cmd + ' ' : null)}
          style={{
            all: 'unset',
            cursor: 'pointer',
            padding: '8px 14px',
            borderRadius: 6,
            border: `1px solid ${theme.border}`,
            background: theme.surface1,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: q.cmd ? accent : theme.textPrimary,
          }}
        >
          {q.label}
        </button>
      ))}
    </div>
  )
}
