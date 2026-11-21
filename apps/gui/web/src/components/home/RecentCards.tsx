import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { ConversationSummary } from '../../lib/types'

/** Earlier conversations as a plain list: the title in the reading face, then
 *  date, agent and cost. Each line is one button. */
export function RecentCards({
  theme,
  accent,
  items,
  onOpenHistory,
  onOpenAll,
}: {
  theme: Theme
  accent: string
  items: ConversationSummary[]
  onOpenHistory: (id: string) => void
  onOpenAll: () => void
}) {
  if (items.length === 0) {
    return (
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
          color: theme.textDisabled,
        }}
      >
        no other conversations yet
      </div>
    )
  }

  const serif = theme.read === JARVIS_FONTS.serif
  return (
    <>
      <ul
        style={{
          listStyle: 'none',
          margin: 0,
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
      >
        {items.map((c) => (
          <li key={c.id}>
            <button
              onClick={() => onOpenHistory(c.id)}
              style={{
                background: 'none',
                border: 0,
                padding: 0,
                margin: 0,
                cursor: 'pointer',
                display: 'block',
                width: '100%',
                textAlign: 'left',
                fontFamily: theme.read,
                fontSize: serif ? 17 : 14,
                lineHeight: 1.5,
                color: theme.textPrimary,
              }}
            >
              <span
                style={{
                  textDecoration: 'underline',
                  textDecorationColor: theme.borderStrong,
                  textUnderlineOffset: 3,
                }}
              >
                {c.title}
              </span>
              <span
                style={{
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 12,
                  color: theme.textSecondary,
                  marginLeft: 10,
                  whiteSpace: 'nowrap',
                }}
              >
                {c.date}
                {c.agents.length > 0 && <> · {speakerLabel(c.agents[0])}</>}
                {' · '}${c.cost.toFixed(4)}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <button
        onClick={onOpenAll}
        style={{
          background: 'none',
          border: 0,
          padding: 0,
          margin: '12px 0 0',
          cursor: 'pointer',
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
          lineHeight: 1.5,
          color: accent,
          textDecoration: 'underline',
          textUnderlineOffset: 3,
        }}
      >
        all conversations →
      </button>
    </>
  )
}
