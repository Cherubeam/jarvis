import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { CostWeekDay } from '../../lib/types'

/** The week's cost as a margin note: the total, the number of conversations,
 *  and one small bar per day between the first and last date. An expensive day
 *  is the only bar that gets a colour. */
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
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 12,
        lineHeight: 1.5,
        color: theme.stats,
      }}
    >
      <div>Cost this week</div>
      <div style={{ color: theme.textPrimary }}>${total.toFixed(4)}</div>
      <div>
        {conversationCount} {conversationCount === 1 ? 'conversation' : 'conversations'}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span>{days[0]?.date.slice(5)}</span>
        <span
          role="img"
          aria-label={days.map((d) => `${d.date}: $${d.cost.toFixed(4)}`).join(', ')}
          style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 18, flexShrink: 0 }}
        >
          {days.map((d) => {
            const h = d.cost === 0 ? 2 : Math.max(3, Math.round((d.cost / max) * 18))
            const isHigh = d.cost > 0.05
            return (
              <span
                key={d.date}
                title={`${d.date}: $${d.cost.toFixed(4)}`}
                style={{
                  width: 6,
                  height: h,
                  background: isHigh ? theme.costHigh : theme.borderStrong,
                }}
              />
            )
          })}
        </span>
        <span>{days[days.length - 1]?.date.slice(5)}</span>
      </div>
    </div>
  )
}
