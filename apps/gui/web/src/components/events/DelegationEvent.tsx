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
    <Row theme={theme} label="" dense={dense}>
      <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 13, color: theme.textSecondary }}>
        Delegating {speakerLabel(e.from)}
        {' → '}
        <span style={{ color: theme.assistant }}>{speakerLabel(e.to)}</span> · {e.reason}
      </div>
    </Row>
  )
}
