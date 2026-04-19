import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import { Row } from './Row'

export function UserEvent({
  e,
  theme,
  dense,
}: {
  e: { text: string }
  theme: Theme
  dense?: boolean
}) {
  const isSlash = e.text.startsWith('/')
  return (
    <Row theme={theme} accent={theme.user} label="You" labelColor={theme.user} dense={dense}>
      <div
        style={{
          fontFamily: isSlash ? JARVIS_FONTS.mono : JARVIS_FONTS.sans,
          fontSize: isSlash ? 14 : 15,
          color: isSlash ? theme.user : theme.textPrimary,
          whiteSpace: 'pre-wrap',
        }}
      >
        {e.text}
      </div>
    </Row>
  )
}
