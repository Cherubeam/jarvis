import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { RagMatch } from '../../lib/types'
import { Row } from './Row'

/** Recall results: what was searched, then each hit as a quoted line with its
 *  date and source underneath. A thin guide line groups them; no cards. */
export function RagEvent({
  e,
  theme,
  dense,
}: {
  e: { query: string; matches: RagMatch[] }
  theme: Theme
  dense?: boolean
}) {
  return (
    <Row theme={theme} label="" dense={dense}>
      <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 13, color: theme.textSecondary }}>
        recall · <span style={{ color: theme.textPrimary }}>"{e.query}"</span> · {e.matches.length}{' '}
        matches
      </div>
      <div
        style={{
          margin: '6px 0 2px 5px',
          padding: '2px 0 2px 14px',
          borderLeft: `1px solid ${theme.borderStrong}`,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        {e.matches.map((m, i) => (
          <div key={i}>
            <div style={{ fontFamily: theme.read, fontSize: 15, color: theme.textPrimary, lineHeight: 1.5, fontStyle: 'italic' }}>
              {m.snippet}
            </div>
            <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.stats }}>
              {m.date} · score {m.score.toFixed(2)} · {m.source}
            </div>
          </div>
        ))}
      </div>
    </Row>
  )
}
