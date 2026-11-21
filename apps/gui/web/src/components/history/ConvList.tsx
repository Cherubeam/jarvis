// ConvList — date-bucketed list with sticky headers, laid out as journal rows:
// the day in the gutter, the title in the reading face, and who / how long /
// how much as a note under it (the pane is narrow, so `.jr-margin` folds below).

import { BUCKET_ORDER, dateBucket, type DateBucket } from '../../lib/dateBucket'
import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { ConversationSummary } from '../../lib/types'

export function ConvList({
  theme,
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

  const serif = theme.read === JARVIS_FONTS.serif

  return (
    <div className="jr-pane" style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingBottom: 16 }}>
      {orderedBuckets.map((b: DateBucket) => (
        <div key={b}>
          <div style={{ position: 'sticky', top: 0, zIndex: 1, background: theme.surface0 }}>
            <div className="jr-row" style={{ paddingTop: 14, paddingBottom: 4 }}>
              <div className="jr-gutter" />
              <h2
                style={{
                  margin: 0,
                  paddingBottom: 6,
                  borderBottom: `1px solid ${theme.border}`,
                  fontFamily: JARVIS_FONTS.serif,
                  fontSize: 18,
                  fontWeight: 600,
                  lineHeight: 1.3,
                  color: theme.textPrimary,
                }}
              >
                {b}
              </h2>
            </div>
          </div>
          {groups[b].map((c) => {
            const active = c.id === selectedId
            // A slash command is something you typed, so it stays in mono.
            const typed = c.title.startsWith('/')
            return (
              <button
                key={c.id}
                onClick={() => onSelect(c.id)}
                aria-current={active ? 'true' : undefined}
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  boxSizing: 'border-box',
                  display: 'block',
                  width: '100%',
                  background: active ? theme.surface2 : 'transparent',
                }}
              >
                <div className="jr-row dense" style={{ paddingTop: 7, paddingBottom: 7 }}>
                  <div
                    className="jr-gutter"
                    style={{
                      fontFamily: JARVIS_FONTS.mono,
                      fontSize: 12,
                      color: theme.textDisabled,
                    }}
                  >
                    {c.date.slice(5)}
                  </div>
                  <div
                    style={{
                      minWidth: 0,
                      fontFamily: typed ? JARVIS_FONTS.mono : theme.read,
                      fontSize: typed || !serif ? 14 : 16,
                      lineHeight: 1.4,
                      color: theme.textPrimary,
                      overflowWrap: 'anywhere',
                    }}
                  >
                    {c.title}
                  </div>
                  <div
                    className="jr-margin"
                    style={{
                      minWidth: 0,
                      fontFamily: JARVIS_FONTS.mono,
                      fontSize: 12,
                      color: theme.stats,
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'baseline',
                      gap: '0 6px',
                    }}
                  >
                    {c.agents.length > 0 ? (
                      <span style={{ color: theme.textSecondary }}>{speakerLabel(c.agents[0])}</span>
                    ) : (
                      <span>—</span>
                    )}
                    {c.agents.length > 1 && <span>+{c.agents.length - 1}</span>}
                    <span>·</span>
                    <span>{c.messages} msg</span>
                    <span style={{ marginLeft: 'auto' }}>${c.cost.toFixed(4)}</span>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}
