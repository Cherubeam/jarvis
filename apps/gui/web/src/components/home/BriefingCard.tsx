import { Markdown } from '../../lib/markdown'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { Briefing } from '../../lib/types'

export function BriefingCard({
  theme,
  briefing,
  today,
}: {
  theme: Theme
  briefing: Briefing | null
  today: string
}) {
  const stale = briefing !== null && briefing.date !== today
  const time = briefing?.generated_at?.slice(11, 16)
  const meta = !briefing
    ? null
    : [
        stale ? `from ${briefing.date}` : time,
        briefing.cost_usd != null ? `$${briefing.cost_usd.toFixed(4)}` : null,
      ]
        .filter(Boolean)
        .join(' · ')
  return (
    <div
      style={{
        background: theme.surface1,
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        padding: '16px 18px 14px',
        marginBottom: 20,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: theme.textPrimary }}>
          Morning briefing
        </div>
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 10.5,
            color: stale ? theme.error : theme.textDisabled,
            marginLeft: 'auto',
          }}
        >
          {meta}
        </div>
      </div>
      {briefing ? (
        <>
          <div style={{ fontSize: 13.5, color: theme.textPrimary }}>
            <Markdown text={briefing.text} theme={theme} />
          </div>
          {briefing.missing_sources.length > 0 && (
            <div
              style={{
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 10.5,
                color: theme.textDisabled,
                marginTop: 8,
              }}
            >
              not available: {briefing.missing_sources.join(', ')}
            </div>
          )}
        </>
      ) : (
        <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.textDisabled }}>
          no briefing yet: run jarvis run-job morning-briefing
        </div>
      )}
    </div>
  )
}
