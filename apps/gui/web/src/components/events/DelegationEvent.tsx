import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import { Row } from './Row'

export function DelegationEvent({
  e,
  theme,
  dense,
}: {
  e: { from: string; to: string; reason: string }
  theme: Theme
  dense?: boolean
}) {
  return (
    <Row theme={theme} label="→" labelColor={theme.system} mono dense={dense}>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12.5,
          color: theme.system,
          letterSpacing: 0.2,
        }}
      >
        Delegating <span style={{ color: theme.textPrimary }}>{speakerLabel(e.from)}</span>
        {' → '}
        <span style={{ color: theme.assistant, fontWeight: 600 }}>{speakerLabel(e.to)}</span>
        <span style={{ color: theme.textSecondary }}> · {e.reason}</span>
      </div>
    </Row>
  )
}
