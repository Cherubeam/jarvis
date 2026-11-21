import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { QuickStartEntry } from '../../lib/types'

/** Ways to start a chat, as one wrapping line of links. */
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
    <div style={{ display: 'flex', gap: '6px 22px', flexWrap: 'wrap' }}>
      {items.map((q, i) => (
        <button
          key={i}
          onClick={() => onStartChat(q.cmd ? q.cmd + ' ' : null)}
          style={{
            background: 'none',
            border: 0,
            padding: 0,
            margin: 0,
            cursor: 'pointer',
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 13,
            lineHeight: 1.5,
            color: q.cmd ? accent : theme.textPrimary,
            textDecoration: 'underline',
            textUnderlineOffset: 3,
          }}
        >
          {q.label}
        </button>
      ))}
    </div>
  )
}
