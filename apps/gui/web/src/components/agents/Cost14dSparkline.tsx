// Per-agent 14-day cost sparkline: one bar per day in a single colour, a
// hairline for a day without spend, and the date range and total under it.

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

export function Cost14dSparkline({
  theme,
  hue,
  days,
  total,
}: {
  theme: Theme
  hue: string
  days: { date: string; cost: number }[]
  total: number
}) {
  const max = Math.max(...days.map((d) => d.cost), 0.0001)
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 60 }}>
        {days.map((d) => {
          const h = d.cost === 0 ? 1 : Math.max(4, Math.round((d.cost / max) * 56))
          return (
            <div
              key={d.date}
              title={`${d.date}: $${d.cost.toFixed(4)}`}
              style={{
                flex: 1,
                height: h,
                background: d.cost === 0 ? theme.borderStrong : hue,
              }}
            />
          )
        })}
      </div>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          gap: '0 12px',
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.stats,
          marginTop: 8,
        }}
      >
        <span>{days[0]?.date}</span>
        <span>total ${total.toFixed(4)}</span>
        <span>{days[days.length - 1]?.date}</span>
      </div>
    </div>
  )
}
