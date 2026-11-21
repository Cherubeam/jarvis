import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { SessionMeta } from '../lib/types'

/** One quiet line at the bottom: who answers, which model, what the session
 *  has cost so far. */
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
        flexShrink: 0,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        padding: '6px 28px 8px',
        gap: '2px 18px',
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 12,
        color: theme.stats,
      }}
    >
      <span>{agent}</span>
      {session && (
        <span>
          {session.model_short} via {session.provider}
        </span>
      )}
      {showStats ? (
        <span style={{ marginLeft: 'auto', display: 'inline-flex', flexWrap: 'wrap', gap: '2px 18px' }}>
          <span>{totals.messages} msgs</span>
          <span>{totals.tokens.toLocaleString()} tokens</span>
          <span style={{ color: totals.cost > 0.05 ? theme.costHigh : theme.cost }}>
            ${totals.cost.toFixed(4)}
          </span>
        </span>
      ) : (
        session && <span style={{ marginLeft: 'auto' }}>started {session.started_at}</span>
      )}
    </div>
  )
}
