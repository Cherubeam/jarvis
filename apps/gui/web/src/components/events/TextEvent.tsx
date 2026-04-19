import { Markdown } from '../../lib/markdown'
import { speakerLabel } from '../../lib/speakerLabel'
import { type Theme } from '../../lib/tokens'
import type { Stats } from '../../lib/types'
import { StatsLine } from '../StatsLine'
import { Row } from './Row'

export function TextEvent({
  e,
  theme,
  dense,
  showStats,
}: {
  e: { agent: string; markdown: string; stats?: Stats }
  theme: Theme
  dense?: boolean
  showStats: boolean
}) {
  const agent = e.agent || 'JARVIS'
  const label = speakerLabel(agent)
  return (
    <Row
      theme={theme}
      accent={theme.assistant}
      label={label}
      labelColor={theme.assistant}
      mono={agent !== 'JARVIS'}
      dense={dense}
    >
      <Markdown text={e.markdown} theme={theme} />
      {showStats && <StatsLine stats={e.stats} theme={theme} />}
    </Row>
  )
}
