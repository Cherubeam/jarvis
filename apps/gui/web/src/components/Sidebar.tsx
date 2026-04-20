// Chat-view sidebar: lists the 20 most recent conversations.
// Phase 2: replaces the FAKE_CONVERSATIONS placeholder with a live fetch
// from /api/conversations.

import { useEffect, useState } from 'react'

import { hueFor } from '../lib/agentHues'
import { speakerLabel } from '../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { ConversationListResponse, ConversationSummary, SessionMeta } from '../lib/types'
import { Icon } from './Icon'

const LIMIT = 20

export function Sidebar({
  theme,
  accent,
  visible,
  session,
  refreshToken,
  onOpen,
}: {
  theme: Theme
  accent: string
  visible: boolean
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

      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 8px' }}>
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
        {!loading &&
          !error &&
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
