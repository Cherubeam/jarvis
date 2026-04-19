import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import { Row } from './Row'

export function ThinkingEvent({ theme, agent }: { theme: Theme; agent: string }) {
  return (
    <Row theme={theme} accent={theme.assistant} label={speakerLabel(agent)} labelColor={theme.assistant}>
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 10,
          color: theme.textSecondary,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
        }}
      >
        <span className="dots">
          <span>·</span>
          <span>·</span>
          <span>·</span>
        </span>
        Thinking…
      </div>
    </Row>
  )
}
