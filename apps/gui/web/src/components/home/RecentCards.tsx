import { hueFor } from '../../lib/agentHues'
import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { ConversationSummary } from '../../lib/types'

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
          fontSize: 12,
          color: theme.textDisabled,
          padding: '6px 0',
        }}
      >
        no other conversations yet
      </div>
    )
  }

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {items.map((c) => {
          const agentHue = c.agents.length > 0 ? hueFor(c.agents[0], accent) : accent
          return (
            <button
              key={c.id}
              onClick={() => onOpenHistory(c.id)}
              style={{
                all: 'unset',
                cursor: 'pointer',
                boxSizing: 'border-box',
                background: theme.surface1,
                border: `1px solid ${theme.border}`,
                borderLeft: `2px solid ${agentHue}`,
                borderRadius: 6,
                padding: '12px 14px',
              }}
            >
              <div
                style={{
                  fontSize: 13,
                  color: theme.textPrimary,
                  lineHeight: 1.35,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  marginBottom: 4,
                }}
              >
                {c.title}
              </div>
              <div
                style={{
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 10.5,
                  color: theme.textSecondary,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <span>{c.date}</span>
                {c.agents.length > 0 && (
                  <>
                    <span>·</span>
                    <span style={{ color: agentHue }}>{speakerLabel(c.agents[0])}</span>
                  </>
                )}
                <span style={{ marginLeft: 'auto', color: theme.cost }}>
                  ${c.cost.toFixed(4)}
                </span>
              </div>
            </button>
          )
        })}
      </div>
      <button
        onClick={onOpenAll}
        style={{
          all: 'unset',
          cursor: 'pointer',
          marginTop: 10,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color: theme.textSecondary,
        }}
      >
        all conversations →
      </button>
    </>
  )
}
