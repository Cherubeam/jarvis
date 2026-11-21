import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { Stats } from '../lib/types'

/** Tokens, cost and timing for one answer. Stacked, so it reads as a margin
 *  note; `compact` puts it on one line for tight places. An expensive answer
 *  is the only one whose cost gets a colour. */
export function StatsLine({
  stats,
  theme,
  compact = false,
}: {
  stats: Stats | undefined
  theme: Theme
  compact?: boolean
}) {
  if (!stats) return null
  const fmt = (n: number) => n.toLocaleString()
  const secs = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`)
  const cost = stats.cost && stats.cost > 0 ? `$${stats.cost.toFixed(4)}` : null
  const costHigh = (stats.cost ?? 0) > 0.01

  return (
    <div
      style={{
        fontFamily: JARVIS_FONTS.mono,
        fontSize: compact ? 11 : 12,
        lineHeight: 1.5,
        color: theme.stats,
        display: 'flex',
        flexDirection: compact ? 'row' : 'column',
        flexWrap: 'wrap',
        gap: compact ? '0 12px' : 0,
      }}
    >
      <span>{fmt(stats.tokens ?? 0)} tokens</span>
      {cost && <span style={{ color: costHigh ? theme.costHigh : theme.cost }}>{cost}</span>}
      <span>
        {secs(stats.total ?? 0)}, first token {secs(stats.ttft ?? 0)}
      </span>
    </div>
  )
}
