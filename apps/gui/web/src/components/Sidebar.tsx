// Chat-view sidebar: lists the 20 most recent conversations.
// Phase 2: replaces the FAKE_CONVERSATIONS placeholder with a live fetch
// from /api/conversations.
// Phase 4: adds a togglable timeline variant (mode='timeline') that reshapes
// the same list as a vertical day-axis with token-sized cards. List-variant
// markup is unchanged.

import { useEffect, useMemo, useState } from 'react'

import { hueFor } from '../lib/agentHues'
import { parseLocalDate } from '../lib/dateBucket'
import { speakerLabel } from '../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { ConversationListResponse, ConversationSummary, SessionMeta } from '../lib/types'
import { Icon } from './Icon'

const LIMIT = 20

export type SidebarMode = 'list' | 'timeline'

export function Sidebar({
  theme,
  accent,
  visible,
  mode,
  session,
  refreshToken,
  onOpen,
}: {
  theme: Theme
  accent: string
  visible: boolean
  mode: SidebarMode
  session: SessionMeta | null
  /** Bumped by App on turn_finished so the list re-fetches without reload. */
  refreshToken: number
  /** Called when the user clicks a row — App routes to History view. */
  onOpen: (id: string) => void
}) {
  const [items, setItems] = useState<ConversationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!visible) return
    setLoading(true)
    setError(null)
    const ac = new AbortController()
    fetch(`/api/conversations?limit=${LIMIT}&sort=recent`, { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<ConversationListResponse>
      })
      .then((data) => {
        setItems(data.items)
        setLoading(false)
      })
      .catch((e) => {
        if (e.name === 'AbortError') return
        setError(String(e.message || e))
        setLoading(false)
      })
    return () => ac.abort()
  }, [visible, refreshToken])

  if (!visible) return null

  const activeFileId = session?.file_id

  return (
    <aside
      style={{
        width: 280,
        flexShrink: 0,
        background: theme.surface1,
        borderRight: `1px solid ${theme.border}`,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '14px 16px 10px', borderBottom: `1px solid ${theme.border}` }}>
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: theme.textDisabled,
            letterSpacing: 1.5,
            textTransform: 'uppercase',
            marginBottom: 10,
          }}
        >
          Conversations
        </div>
        {/* Search input is inert — will be wired in a later phase. */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: theme.surface2,
            borderRadius: 6,
            padding: '6px 10px',
            border: `1px solid ${theme.border}`,
          }}
        >
          <Icon name="search" size={12} color={theme.textDisabled} />
          <input
            placeholder="Search or ask recall…"
            style={{
              all: 'unset',
              flex: 1,
              fontFamily: JARVIS_FONTS.sans,
              fontSize: 12.5,
              color: theme.textPrimary,
            }}
          />
          <span
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 10,
              color: theme.textDisabled,
              padding: '1px 5px',
              border: `1px solid ${theme.border}`,
              borderRadius: 3,
            }}
          >
            ⌘K
          </span>
        </div>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: mode === 'timeline' ? '8px 12px 16px 8px' : '6px 8px',
          boxSizing: 'border-box',
        }}
      >
        {loading &&
          [0, 1, 2].map((i) => (
            <div
              key={i}
              style={{
                padding: '8px 10px',
                marginBottom: 2,
                opacity: 0.5,
              }}
            >
              <div
                style={{
                  height: 10,
                  width: '35%',
                  background: theme.surface2,
                  borderRadius: 2,
                  marginBottom: 6,
                }}
              />
              <div
                style={{
                  height: 12,
                  width: '85%',
                  background: theme.surface2,
                  borderRadius: 2,
                }}
              />
            </div>
          ))}
        {error && !loading && (
          <div
            style={{
              padding: '12px 10px',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              color: theme.error,
            }}
          >
            load failed
          </div>
        )}
        {!loading &&
          !error &&
          items.length === 0 &&
          (
            <div
              style={{
                padding: '12px 10px',
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 11,
                color: theme.textDisabled,
              }}
            >
              no conversations yet
            </div>
          )}
        {!loading && !error && items.length > 0 && mode === 'list' &&
          items.map((c) => {
            const active = c.id === activeFileId
            const hue = hueFor(c.agents[0], accent)
            return (
              <button
                key={c.id}
                onClick={() => onOpen(c.id)}
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  display: 'block',
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '8px 10px',
                  borderRadius: 6,
                  marginBottom: 2,
                  background: active ? theme.surface2 : 'transparent',
                  borderLeft: active ? `2px solid ${hue}` : '2px solid transparent',
                }}
              >
                <div
                  style={{
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 10.5,
                    color: theme.textDisabled,
                    marginBottom: 2,
                  }}
                >
                  {c.date}
                </div>
                <div
                  style={{
                    fontSize: 13,
                    color: theme.textPrimary,
                    lineHeight: 1.35,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {c.title}
                </div>
                <div
                  style={{
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 10.5,
                    color: theme.textSecondary,
                    marginTop: 3,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  {c.agents.length > 0 && (
                    <span style={{ color: hue }}>{speakerLabel(c.agents[0])}</span>
                  )}
                  {c.agents.length > 0 && (
                    <span style={{ color: theme.textDisabled }}>·</span>
                  )}
                  <span>{c.messages} msg</span>
                  <span style={{ marginLeft: 'auto', color: theme.cost }}>
                    ${c.cost.toFixed(4)}
                  </span>
                </div>
              </button>
            )
          })}
        {!loading && !error && items.length > 0 && mode === 'timeline' && (
          <TimelineRows
            items={items}
            activeFileId={activeFileId}
            theme={theme}
            accent={accent}
            onOpen={onOpen}
          />
        )}
      </div>

      {session && (
        <div
          style={{
            padding: '10px 16px',
            borderTop: `1px solid ${theme.border}`,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 10.5,
            color: theme.textDisabled,
            lineHeight: 1.6,
          }}
        >
          {session.vault && (
            <div>
              vault: <span style={{ color: theme.textSecondary }}>{session.vault}</span>
            </div>
          )}
          <div>
            data: <span style={{ color: theme.textSecondary }}>~/jarvis/data</span>
          </div>
        </div>
      )}
    </aside>
  )
}

// -- Timeline variant ------------------------------------------------------

type TimelineRow = {
  conv: ConversationSummary
  isFirstOfDay: boolean
  dayCost: number   // sum of cost across all convs on this calendar day; only shown on first-of-day
  weekday: string   // "Sun" / "Mon" / …; only shown on first-of-day
  dayNum: string    // "14"; only shown on first-of-day
}

// Convert flat conversation list into timeline rows, stamping first-of-day markers
// and per-day cost sums. Items are already sorted by recency from /api/conversations?sort=recent.
function buildTimelineRows(items: ConversationSummary[]): TimelineRow[] {
  const dayCosts = new Map<string, number>()
  for (const c of items) dayCosts.set(c.date, (dayCosts.get(c.date) ?? 0) + c.cost)

  const seen = new Set<string>()
  const rows: TimelineRow[] = []
  for (const conv of items) {
    const isFirstOfDay = !seen.has(conv.date)
    seen.add(conv.date)
    const d = parseLocalDate(conv.date)
    rows.push({
      conv,
      isFirstOfDay,
      dayCost: dayCosts.get(conv.date) ?? 0,
      weekday: isFirstOfDay ? d.toLocaleDateString('en-US', { weekday: 'short' }) : '',
      dayNum: isFirstOfDay ? String(d.getDate()) : '',
    })
  }
  return rows
}

// Token-driven height: logarithmic so long conversations don't dominate.
// Stable across refreshes (no dynamic max).
function heightFor(tokens: number): number {
  const base = 48
  const span = 32
  const t = Math.max(tokens || 0, 100)
  const scaled = Math.round(Math.log10(t) * 8)
  return Math.max(base, Math.min(base + span, base + scaled))
}

function TimelineRows({
  items,
  activeFileId,
  theme,
  accent,
  onOpen,
}: {
  items: ConversationSummary[]
  activeFileId: string | undefined
  theme: Theme
  accent: string
  onOpen: (id: string) => void
}) {
  const rows = useMemo(() => buildTimelineRows(items), [items])

  return (
    <div>
      {rows.map(({ conv, isFirstOfDay, dayCost, weekday, dayNum }) => {
        const active = conv.id === activeFileId
        const hue = hueFor(conv.agents[0], accent)
        const cardH = heightFor(conv.tokens)
        return (
          <div
            key={conv.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '40px 1fr',
              columnGap: 10,
              alignItems: 'stretch',
              padding: '3px 0',
            }}
          >
            <div
              style={{
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 10,
                lineHeight: 1.25,
                textAlign: 'right',
                paddingTop: 4,
                display: 'flex',
                flexDirection: 'column',
                gap: 1,
                minWidth: 0,
              }}
            >
              {isFirstOfDay && (
                <>
                  <div style={{ color: theme.textSecondary }}>{weekday}</div>
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: theme.textPrimary,
                      lineHeight: 1.1,
                    }}
                  >
                    {dayNum}
                  </div>
                  <div style={{ color: theme.cost, fontSize: 9.5, marginTop: 2 }}>
                    ${dayCost.toFixed(3)}
                  </div>
                </>
              )}
            </div>

            <div
              style={{
                position: 'relative',
                borderLeft: `1px solid ${theme.border}`,
                paddingLeft: 10,
                display: 'flex',
                alignItems: 'center',
                minWidth: 0,
              }}
            >
              <button
                onClick={() => onOpen(conv.id)}
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  boxSizing: 'border-box',
                  width: '100%',
                  height: cardH,
                  background: active ? theme.surface2 : theme.surface1,
                  border: `1px solid ${active ? hue : theme.border}`,
                  borderLeft: `${active ? 3 : 2}px solid ${hue}`,
                  borderRadius: 5,
                  padding: '6px 9px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  gap: 3,
                  minWidth: 0,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: theme.textPrimary,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    lineHeight: 1.3,
                    width: '100%',
                  }}
                >
                  {conv.title}
                </div>
                <div
                  style={{
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 10,
                    color: theme.textSecondary,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    minWidth: 0,
                    width: '100%',
                  }}
                >
                  {conv.agents.length > 0 && (
                    <span
                      style={{
                        color: hue,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        minWidth: 0,
                        flex: '0 1 auto',
                      }}
                    >
                      {speakerLabel(conv.agents[0])}
                    </span>
                  )}
                  {conv.agents.length > 1 && (
                    <span style={{ color: theme.textDisabled, flexShrink: 0 }}>
                      +{conv.agents.length - 1}
                    </span>
                  )}
                  <span style={{ marginLeft: 'auto', color: theme.textDisabled, flexShrink: 0 }}>
                    {conv.messages} msg
                  </span>
                </div>
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
