import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { RagMatch } from '../../lib/types'
import { Row } from './Row'

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
    <Row theme={theme} label="recall" labelColor={theme.tool} mono dense={dense}>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.textSecondary,
          marginBottom: 6,
        }}
      >
        query: <span style={{ color: theme.textPrimary }}>"{e.query}"</span> · {e.matches.length}{' '}
        matches
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {e.matches.map((m, i) => (
          <div
            key={i}
            style={{
              background: theme.surface2,
              border: `1px solid ${theme.border}`,
              borderRadius: 8,
              padding: '10px 12px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 11,
                color: theme.textSecondary,
                marginBottom: 4,
              }}
            >
              <span style={{ color: theme.assistant }}>{m.date}</span>
              <span>·</span>
              <span>score {m.score.toFixed(2)}</span>
              <span style={{ marginLeft: 'auto', color: theme.textDisabled }}>{m.source}</span>
            </div>
            <div
              style={{
                fontSize: 13.5,
                color: theme.textPrimary,
                lineHeight: 1.55,
                fontStyle: 'italic',
              }}
            >
              {m.snippet}
            </div>
          </div>
        ))}
      </div>
    </Row>
  )
}
