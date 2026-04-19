import { Fragment } from 'react'

import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { SessionMeta } from '../lib/types'

export function StatusBar({
  theme,
  agent,
  totals,
  showStats,
  session,
}: {
  theme: Theme
  agent: string
  totals: { messages: number; tokens: number; cost: number }
  showStats: boolean
  session: SessionMeta | null
}) {
  return (
    <div
      style={{
        height: 28,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: 14,
        background: theme.surface1,
        borderTop: `1px solid ${theme.border}`,
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 11,
        color: theme.textSecondary,
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: theme.user,
            boxShadow: `0 0 6px ${theme.user}`,
          }}
        />
        <span style={{ color: theme.assistant, fontWeight: 600 }}>{agent}</span>
      </span>
      {session && (
        <Fragment>
          <span>·</span>
          <span>
            {session.model_short}{' '}
            <span style={{ color: theme.textDisabled }}>via {session.provider}</span>
          </span>
        </Fragment>
      )}
      {showStats ? (
        <Fragment>
          <span style={{ marginLeft: 'auto' }}>session:</span>
          <span>{totals.messages} msgs</span>
          <span>·</span>
          <span>{totals.tokens.toLocaleString()} tokens</span>
          <span>·</span>
          <span style={{ color: totals.cost > 0.05 ? theme.costHigh : theme.cost }}>
            ${totals.cost.toFixed(4)}
          </span>
        </Fragment>
      ) : (
        session && <span style={{ marginLeft: 'auto' }}>started {session.started_at}</span>
      )}
    </div>
  )
}
