// Per-agent 14-day cost sparkline. Visual feel mirrors home/CostCard.tsx but
// uses the agent's hue instead of theme.cost — signals "this agent's spend"
// rather than "overall cost".

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
    <div
      style={{
        background: theme.surface1,
        border: `1px solid ${theme.border}`,
        borderRadius: 6,
        padding: '16px 18px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 60 }}>
        {days.map((d) => {
          const h = d.cost === 0 ? 2 : Math.max(4, Math.round((d.cost / max) * 56))
          return (
            <div
              key={d.date}
              title={`${d.date}: $${d.cost.toFixed(4)}`}
              style={{
                flex: 1,
                height: h,
                background: d.cost === 0 ? theme.border : hue,
                opacity: d.cost === 0 ? 0.3 : 0.75,
                borderRadius: 1,
              }}
            />
          )
        })}
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 10,
          color: theme.textDisabled,
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
