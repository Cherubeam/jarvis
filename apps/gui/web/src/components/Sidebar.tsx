// Chat-view sidebar: lists the 20 most recent conversations.
// Phase 2: replaces the FAKE_CONVERSATIONS placeholder with a live fetch
// from /api/conversations.
// Phase 4: adds a togglable timeline variant (mode='timeline') that reshapes
// the same list as a vertical day-axis with token-sized entries.
// Journal look: no cards and no agent hues; the open conversation is marked by
// its background alone.

import { useEffect, useMemo, useState, type CSSProperties } from 'react'

import { parseLocalDate } from '../lib/dateBucket'
import { speakerLabel } from '../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { ConversationListResponse, ConversationSummary, SessionMeta } from '../lib/types'

const LIMIT = 20

export type SidebarMode = 'list' | 'timeline'

export function Sidebar({
  theme,
  visible,
  mode,
  session,
  refreshToken,
  onOpen,
  disabled = false,
}: {
  theme: Theme
  accent: string
  visible: boolean
  mode: SidebarMode
  session: SessionMeta | null
  /** Bumped by App on turn_finished so the list re-fetches without reload. */
  refreshToken: number
  /** Called when the user clicks a row. In chat view this resumes the
   * conversation in-place; elsewhere it's a no-op handler set by the parent. */
  onOpen: (id: string) => void
  /** When true (a turn is streaming) rows render grayed-out and refuse clicks. */
  disabled?: boolean
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
            fontSize: 12,
            color: theme.textSecondary,
            marginBottom: 10,
          }}
        >
          Conversations
        </div>
        {/* Search input is inert — will be wired in a later phase. */}
        <div style={{ position: 'relative' }}>
          <input
            placeholder="Search or ask recall…"
            aria-label="Search or ask recall"
            style={{
              boxSizing: 'border-box',
              display: 'block',
              width: '100%',
              minHeight: 36,
              margin: 0,
              padding: '0 40px 0 10px',
              border: `1px solid ${theme.border}`,
              borderRadius: 4,
              background: theme.surface2,
              color: theme.textPrimary,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
            }}
          />
          <span
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: 0,
              right: 10,
              lineHeight: '36px',
              pointerEvents: 'none',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textDisabled,
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
              fontSize: 12,
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
                fontSize: 12,
                color: theme.textDisabled,
              }}
            >
              no conversations yet
            </div>
          )}
        {!loading && !error && items.length > 0 && mode === 'list' &&
          items.map((c) => {
            const active = c.id === activeFileId
            return (
              <button
                key={c.id}
                onClick={() => !disabled && onOpen(c.id)}
                disabled={disabled}
                aria-current={active ? 'true' : undefined}
                title={disabled ? 'Wait for the current turn to finish' : undefined}
                style={{
                  all: 'unset',
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  display: 'block',
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '8px 10px',
                  borderRadius: 4,
                  marginBottom: 2,
                  background: active ? theme.surface3 : 'transparent',
                  opacity: disabled ? 0.5 : 1,
                }}
              >
                <div
                  style={{
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 12,
                    color: theme.textDisabled,
                    marginBottom: 2,
                  }}
                >
                  {c.date}
                </div>
                <div style={titleStyle(c.title, theme)}>{c.title}</div>
                <div
                  style={{
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 12,
                    color: theme.stats,
                    marginTop: 3,
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: 6,
                    minWidth: 0,
                  }}
                >
                  {c.agents.length > 0 && (
                    <span
                      style={{
                        color: theme.textSecondary,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        minWidth: 0,
                      }}
                    >
                      {speakerLabel(c.agents[0])}
                    </span>
                  )}
                  {c.agents.length > 0 && <span>·</span>}
                  <span style={{ flexShrink: 0 }}>{c.messages} msg</span>
                  <span style={{ marginLeft: 'auto', flexShrink: 0 }}>${c.cost.toFixed(4)}</span>
                </div>
              </button>
            )
          })}
        {!loading && !error && items.length > 0 && mode === 'timeline' && (
          <TimelineRows
            items={items}
            activeFileId={activeFileId}
            theme={theme}
            onOpen={onOpen}
            disabled={disabled}
          />
        )}
      </div>

      {session && (
        <div
          style={{
            padding: '10px 16px',
            borderTop: `1px solid ${theme.border}`,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textDisabled,
            lineHeight: 1.6,
            overflowWrap: 'anywhere',
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

// A conversation title on one line. It is text to read, so it takes the reading
// face; a slash command is something you typed and stays in mono.
function titleStyle(title: string, theme: Theme): CSSProperties {
  const typed = title.startsWith('/') || theme.read !== JARVIS_FONTS.serif
  return {
    fontFamily: typed ? JARVIS_FONTS.mono : theme.read,
    fontSize: typed ? 13 : 15,
    lineHeight: 1.35,
    color: theme.textPrimary,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    width: '100%',
  }
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
  onOpen,
  disabled = false,
}: {
  items: ConversationSummary[]
  activeFileId: string | undefined
  theme: Theme
  onOpen: (id: string) => void
  disabled?: boolean
}) {
  const rows = useMemo(() => buildTimelineRows(items), [items])

  return (
    <div>
      {rows.map(({ conv, isFirstOfDay, dayCost, weekday, dayNum }) => {
        const active = conv.id === activeFileId
        const rowH = heightFor(conv.tokens)
        return (
          <div
            key={conv.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '52px minmax(0, 1fr)',
              columnGap: 10,
              alignItems: 'stretch',
            }}
          >
            {/* The day, once per day: weekday, date, what the day cost. */}
            <div
              style={{
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 12,
                lineHeight: 1.3,
                textAlign: 'right',
                paddingTop: 8,
                paddingBottom: 6,
                minWidth: 0,
              }}
            >
              {isFirstOfDay && (
                <>
                  <div style={{ color: theme.textDisabled }}>{weekday}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: theme.textPrimary }}>
                    {dayNum}
                  </div>
                  <div style={{ color: theme.stats }}>${dayCost.toFixed(3)}</div>
                </>
              )}
            </div>

            {/* The axis is a single rule; an entry is text on it, not a card. */}
            <div
              style={{
                borderLeft: `1px solid ${theme.border}`,
                padding: '2px 0 2px 6px',
                display: 'flex',
                alignItems: 'center',
                minWidth: 0,
              }}
            >
              <button
                onClick={() => !disabled && onOpen(conv.id)}
                disabled={disabled}
                aria-current={active ? 'true' : undefined}
                title={disabled ? 'Wait for the current turn to finish' : undefined}
                style={{
                  all: 'unset',
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  boxSizing: 'border-box',
                  width: '100%',
                  minHeight: rowH,
                  background: active ? theme.surface3 : 'transparent',
                  borderRadius: 4,
                  padding: '6px 8px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  gap: 3,
                  minWidth: 0,
                  overflow: 'hidden',
                  opacity: disabled ? 0.5 : 1,
                }}
              >
                <div style={titleStyle(conv.title, theme)}>{conv.title}</div>
                <div
                  style={{
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 12,
                    color: theme.stats,
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: 6,
                    minWidth: 0,
                    width: '100%',
                  }}
                >
                  {conv.agents.length > 0 && (
                    <span
                      style={{
                        color: theme.textSecondary,
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
                    <span style={{ flexShrink: 0 }}>+{conv.agents.length - 1}</span>
                  )}
                  <span style={{ marginLeft: 'auto', flexShrink: 0 }}>{conv.messages} msg</span>
                </div>
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
