import { Markdown } from '../../lib/markdown'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { Briefing } from '../../lib/types'
import { Row } from '../events/Row'

/** The morning briefing as a journal entry: the time it was written in the
 *  gutter, the text in the reading face, its name, cost and missing sources as
 *  a margin note. A briefing from an earlier day says so above the text. */
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
  const serif = theme.read === JARVIS_FONTS.serif
  return (
    <Row
      theme={theme}
      label={stale ? '' : (time ?? '')}
      margin={
        <>
          <div>Morning briefing</div>
          {briefing && briefing.cost_usd != null && <div>${briefing.cost_usd.toFixed(4)}</div>}
          {briefing && briefing.missing_sources.length > 0 && (
            <div>not available: {briefing.missing_sources.join(', ')}</div>
          )}
        </>
      }
    >
      {briefing ? (
        <>
          {stale && (
            <div
              style={{
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 12,
                color: theme.error,
                marginBottom: 4,
              }}
            >
              from {briefing.date}
            </div>
          )}
          <div
            style={{
              fontFamily: theme.read,
              fontSize: serif ? 17.5 : 14,
              lineHeight: 1.6,
              color: theme.textPrimary,
            }}
          >
            <Markdown text={briefing.text} theme={theme} />
          </div>
        </>
      ) : (
        <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 13, color: theme.textDisabled }}>
          no briefing yet: run jarvis run-job morning-briefing
        </div>
      )}
    </Row>
  )
}
