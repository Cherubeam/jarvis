import { Fragment } from 'react'

import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { Stats } from '../lib/types'

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
  const cost = stats.cost && stats.cost > 0 ? `$${stats.cost.toFixed(4)}` : null
  const costHigh = (stats.cost ?? 0) > 0.01

  return (
    <div
      style={{
        fontFamily: JARVIS_FONTS.mono,
        fontSize: compact ? 11 : 12,
        color: theme.stats,
        letterSpacing: 0.2,
        marginTop: compact ? 4 : 8,
      }}
    >
      [{fmt(stats.tokens ?? 0)} tokens
      {cost && (
        <Fragment>
          {' '}
          <span style={{ opacity: 0.5 }}>|</span>{' '}
          <span style={{ color: costHigh ? theme.costHigh : theme.cost }}>{cost}</span>
        </Fragment>
      )}{' '}
      <span style={{ opacity: 0.5 }}>|</span> TTFT: {stats.ttft ?? 0}ms{' '}
      <span style={{ opacity: 0.5 }}>|</span> Total: {stats.total ?? 0}ms]
    </div>
  )
}
