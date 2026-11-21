import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import { Row } from './Row'

/** What you typed, in mono. The gutter shows when; a replayed turn has no time
 *  on record, so it says "you" instead. */
export function UserEvent({
  e,
  theme,
  dense,
}: {
  e: { text: string; time?: string }
  theme: Theme
  dense?: boolean
}) {
  return (
    <Row theme={theme} label={e.time || 'you'} dense={dense}>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 14,
          color: theme.textPrimary,
          whiteSpace: 'pre-wrap',
        }}
      >
        {e.text}
      </div>
    </Row>
  )
}
