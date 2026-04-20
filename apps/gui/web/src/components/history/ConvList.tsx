// ConvList — date-bucketed list with sticky headers.
// Ported from JARVIS GUI.html 3217-3285.

import { hueFor } from '../../lib/agentHues'
import { BUCKET_ORDER, dateBucket, type DateBucket } from '../../lib/dateBucket'
import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { ConversationSummary } from '../../lib/types'

export function ConvList({
  theme,
  accent,
  conversations,
  selectedId,
  onSelect,
}: {
  theme: Theme
  accent: string
  conversations: ConversationSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  if (conversations.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.textDisabled,
          padding: 32,
          textAlign: 'center',
        }}
      >
        no conversations match these filters
      </div>
    )
  }

  const groups: Record<string, ConversationSummary[]> = {}
  conversations.forEach((c) => {
    const b = dateBucket(c.date)
    ;(groups[b] = groups[b] || []).push(c)
  })
  const orderedBuckets = BUCKET_ORDER.filter((b) => groups[b])

  return (
    <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
      {orderedBuckets.map((b: DateBucket) => (
        <div key={b}>
          <div
            style={{
              padding: '10px 16px 4px',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 9.5,
              letterSpacing: 1.3,
              color: theme.textDisabled,
              textTransform: 'uppercase',
              position: 'sticky',
              top: 0,
              background: theme.surface1,
              zIndex: 1,
            }}
          >
            {b}
          </div>
          {groups[b].map((c) => {
            const active = c.id === selectedId
            const hue = hueFor(c.agents[0], accent)
            return (
              <button
                key={c.id}
                onClick={() => onSelect(c.id)}
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  boxSizing: 'border-box',
                  display: 'block',
                  width: '100%',
                  padding: '10px 16px 11px',
                  borderLeft: `3px solid ${active ? hue : 'transparent'}`,
                  background: active ? theme.surface2 : 'transparent',
                  borderBottom: `1px solid ${theme.border}`,
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
                  {c.agents.length > 0 ? (
                    <span style={{ color: hue }}>{speakerLabel(c.agents[0])}</span>
                  ) : (
                    <span style={{ color: theme.textDisabled }}>—</span>
                  )}
                  {c.agents.length > 1 && (
                    <span style={{ color: theme.textDisabled }}>+{c.agents.length - 1}</span>
                  )}
                  <span style={{ color: theme.textDisabled }}>·</span>
                  <span>{c.messages} msg</span>
                  <span style={{ marginLeft: 'auto', color: theme.cost }}>
                    ${c.cost.toFixed(4)}
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}
