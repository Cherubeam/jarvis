import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import { Row } from './Row'

export function SystemEvent({
  e,
  theme,
  dense,
  isError,
}: {
  e: { text: string }
  theme: Theme
  dense?: boolean
  isError?: boolean
}) {
  return (
    <Row theme={theme} label="" dense={dense}>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
          color: isError ? theme.error : theme.system,
        }}
      >
        {e.text}
      </div>
    </Row>
  )
}
