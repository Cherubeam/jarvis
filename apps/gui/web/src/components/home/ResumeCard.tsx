import { hueFor } from '../../lib/agentHues'
import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { ConversationSummary } from '../../lib/types'

export function ResumeCard({
  theme,
  accent,
  resume,
  onResume,
}: {
  theme: Theme
  accent: string
  resume: ConversationSummary | null
  onResume: () => void
}) {
  if (!resume) {
    return (
      <div
        style={{
          background: theme.surface1,
          border: `1px solid ${theme.border}`,
          borderLeft: `3px solid ${theme.border}`,
          borderRadius: 8,
          padding: '18px 20px',
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.textDisabled,
        }}
      >
        no prior sessions · start a new chat below
      </div>
    )
  }

  const agentHue = resume.agents.length > 0 ? hueFor(resume.agents[0], accent) : accent
  return (
    <button
      onClick={onResume}
      style={{
        all: 'unset',
        cursor: 'pointer',
        boxSizing: 'border-box',
        display: 'block',
        width: '100%',
        background: theme.surface1,
        border: `1px solid ${theme.border}`,
        borderLeft: `3px solid ${accent}`,
        borderRadius: 8,
        padding: '18px 20px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: theme.textPrimary,
              lineHeight: 1.3,
              marginBottom: 6,
            }}
          >
            {resume.title}
          </div>
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              color: theme.textSecondary,
              display: 'flex',
              gap: 8,
              flexWrap: 'wrap',
            }}
          >
            <span>{resume.date}</span>
            <span>·</span>
            <span>{resume.messages} messages</span>
            <span>·</span>
            <span>{resume.tokens.toLocaleString()} tokens</span>
            <span>·</span>
            <span style={{ color: theme.cost }}>${resume.cost.toFixed(4)}</span>
            {resume.agents.length > 0 && (
              <>
                <span>·</span>
                <span style={{ color: agentHue }}>{speakerLabel(resume.agents[0])}</span>
                {resume.agents.length > 1 && (
                  <span style={{ color: theme.textDisabled }}>+{resume.agents.length - 1}</span>
                )}
              </>
            )}
          </div>
        </div>
        <span
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: accent,
            fontWeight: 700,
            padding: '6px 10px',
            border: `1px solid ${accent}60`,
            borderRadius: 4,
            flexShrink: 0,
          }}
        >
          resume →
        </span>
      </div>
    </button>
  )
}
