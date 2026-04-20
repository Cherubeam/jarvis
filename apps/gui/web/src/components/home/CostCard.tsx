import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { CostWeekDay } from '../../lib/types'

export function CostCard({
  theme,
  days,
  total,
  conversationCount,
}: {
  theme: Theme
  days: CostWeekDay[]
  total: number
  conversationCount: number
}) {
  const max = Math.max(...days.map((d) => d.cost), 0.0001)
  return (
    <div
      style={{
        background: theme.surface1,
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        padding: '16px 18px 14px',
      }}
    >
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: theme.textPrimary,
          marginBottom: 12,
        }}
      >
        Cost this week
      </div>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 28,
          fontWeight: 600,
          color: theme.cost,
          lineHeight: 1,
        }}
      >
        ${total.toFixed(4)}
      </div>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 10.5,
          color: theme.textDisabled,
          marginTop: 4,
        }}
      >
        {conversationCount} {conversationCount === 1 ? 'conversation' : 'conversations'}
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 3,
          height: 40,
          marginTop: 18,
        }}
      >
        {days.map((d) => {
          const h = d.cost === 0 ? 2 : Math.max(3, Math.round((d.cost / max) * 36))
          const isHigh = d.cost > 0.05
          return (
            <div
              key={d.date}
              title={`${d.date}: $${d.cost.toFixed(4)}`}
              style={{
                flex: 1,
                height: h,
                background: d.cost === 0 ? theme.border : isHigh ? theme.costHigh : theme.cost,
                opacity: d.cost === 0 ? 0.5 : 0.7,
                borderRadius: 1.5,
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
          fontSize: 9,
          color: theme.textDisabled,
          marginTop: 5,
        }}
      >
        <span>{days[0]?.date.slice(5)}</span>
        <span>{days[days.length - 1]?.date.slice(5)}</span>
      </div>
    </div>
  )
}
