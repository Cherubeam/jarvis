// One entry of the agent directory: the name (the link to the agent's page)
// followed by its description, the command on a second line, and tool count
// and last use as a margin note. The file keeps its name; it is no longer a card.

import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { Agent } from '../../lib/types'
import { JournalRow, noteStyle, readStyle, textButton } from './journal'

export function AgentCard({
  theme,
  agent,
  lastUsedLabel,
  onClick,
}: {
  theme: Theme
  accent: string
  agent: Agent
  lastUsedLabel: string
  /** Kept for callers; the orchestrator is an entry like every other. */
  featured?: boolean
  onClick: () => void
}) {
  const toolsCount = agent.tools.length
  return (
    <JournalRow
      theme={theme}
      style={{ paddingTop: 8, paddingBottom: 8 }}
      margin={
        <>
          {toolsCount} tool{toolsCount === 1 ? '' : 's'} · {lastUsedLabel}
        </>
      }
    >
      <p style={{ margin: 0, ...readStyle(theme, 18), color: theme.textPrimary }}>
        <button
          onClick={onClick}
          style={{
            ...textButton(theme.textPrimary),
            fontFamily: JARVIS_FONTS.serif,
            fontSize: 18,
            fontWeight: 600,
            textDecoration: 'underline',
            textDecorationThickness: 1,
            textUnderlineOffset: 3,
          }}
        >
          {speakerLabel(agent.name)}
        </button>{' '}
        {agent.description}
      </p>
      {agent.command && (
        <div style={{ ...noteStyle(theme.textSecondary), marginTop: 2 }}>{agent.command}</div>
      )}
    </JournalRow>
  )
}
