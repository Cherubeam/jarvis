// Cards used in the Agents overview grid — featured (JARVIS) + compact (delegates).
// Ported from JARVIS GUI v6 line 1752.

import { hueFor } from '../../lib/agentHues'
import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { Agent } from '../../lib/types'

export function AgentCard({
  theme,
  accent,
  agent,
  lastUsedLabel,
  featured = false,
  onClick,
}: {
  theme: Theme
  accent: string
  agent: Agent
  lastUsedLabel: string
  featured?: boolean
  onClick: () => void
}) {
  const hue = hueFor(agent.name, accent)
  const toolsCount = agent.tools.length
  return (
    <button
      onClick={onClick}
      style={{
        all: 'unset',
        cursor: 'pointer',
        boxSizing: 'border-box',
        display: 'block',
        width: '100%',
        background: featured ? theme.surface2 : theme.surface1,
        border: `1px solid ${featured ? hue : theme.border}`,
        borderLeft: `${featured ? 4 : 3}px solid ${hue}`,
        borderRadius: 7,
        padding: featured ? '18px 20px' : '14px 16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
        <div
          style={{
            fontSize: featured ? 18 : 14,
            fontWeight: 600,
            color: theme.textPrimary,
            letterSpacing: -0.1,
          }}
        >
          {speakerLabel(agent.name)}
        </div>
        {agent.command && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: featured ? 12 : 11,
              color: hue,
            }}
          >
            {agent.command}
          </div>
        )}
      </div>
      <div
        style={{
          fontSize: featured ? 13 : 12,
          color: theme.textSecondary,
          lineHeight: 1.45,
          marginBottom: featured ? 12 : 8,
        }}
      >
        {agent.description}
      </div>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 10,
          color: theme.textDisabled,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span>
          {toolsCount} tool{toolsCount === 1 ? '' : 's'}
        </span>
        <span>·</span>
        <span>{lastUsedLabel}</span>
      </div>
    </button>
  )
}
