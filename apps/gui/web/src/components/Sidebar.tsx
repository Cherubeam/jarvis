import { Icon } from './Icon'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { SessionMeta } from '../lib/types'

// Phase 1: list mode only. Conversations are placeholder fixtures until the
// History view (Phase 2) provides a real index.

const FAKE_CONVERSATIONS = [
  { date: '2026-04-19', title: 'current session', cost: 0, messages: 0, active: true },
  { date: '2026-04-18', title: 'week-12 substack · draft opening', cost: 0.0205, messages: 8 },
  { date: '2026-04-17', title: 'benchmark: qwen vs sonnet (goldens)', cost: 0.0411, messages: 14 },
  { date: '2026-04-16', title: 'navigator · weekly review', cost: 0.0089, messages: 6 },
]

export function Sidebar({
  theme,
  accent,
  visible,
  session,
}: {
  theme: Theme
  accent: string
  visible: boolean
  session: SessionMeta | null
}) {
  if (!visible) return null
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
        {FAKE_CONVERSATIONS.map((c, i) => (
          <div
            key={i}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              marginBottom: 2,
              background: c.active ? theme.surface2 : 'transparent',
              borderLeft: c.active ? `2px solid ${accent}` : '2px solid transparent',
              cursor: 'pointer',
              boxSizing: 'border-box',
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
              }}
            >
              {c.messages} msgs ·{' '}
              <span style={{ color: theme.cost }}>${c.cost.toFixed(4)}</span>
            </div>
          </div>
        ))}
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
