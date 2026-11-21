import { Markdown } from '../../lib/markdown'
import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { Stats } from '../../lib/types'
import { StatsLine } from '../StatsLine'
import { Row } from './Row'

/** An answer, in the reading face. JARVIS needs no label: the typeface already
 *  tells its words from yours. A specialist is named in the gutter. Tokens and
 *  cost sit in the margin, visible but out of the reading line. */
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
  const serif = theme.read === JARVIS_FONTS.serif
  return (
    <Row
      theme={theme}
      label={agent === 'JARVIS' ? '' : speakerLabel(agent)}
      labelColor={theme.assistant}
      dense={dense}
      margin={showStats && e.stats ? <StatsLine stats={e.stats} theme={theme} /> : undefined}
    >
      <div style={{ fontFamily: theme.read, fontSize: serif ? 17.5 : 14, lineHeight: 1.6 }}>
        <Markdown text={e.markdown} theme={theme} />
      </div>
    </Row>
  )
}
