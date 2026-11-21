import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { ConversationSummary } from '../../lib/types'

/** The last conversation as three lines: its title, its numbers, and the link
 *  that picks it up again. The whole block is one button. */
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
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
          color: theme.textDisabled,
        }}
      >
        no prior sessions · start a new chat below
      </div>
    )
  }

  const serif = theme.read === JARVIS_FONTS.serif
  return (
    <button
      onClick={onResume}
      style={{
        background: 'none',
        border: 0,
        padding: 0,
        margin: 0,
        cursor: 'pointer',
        display: 'block',
        width: '100%',
        textAlign: 'left',
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 12,
        lineHeight: 1.5,
        color: theme.textSecondary,
      }}
    >
      <span
        style={{
          display: 'block',
          fontFamily: theme.read,
          fontSize: serif ? 17.5 : 14,
          color: theme.textPrimary,
          lineHeight: 1.5,
        }}
      >
        {resume.title}
      </span>
      <span style={{ display: 'flex', gap: '0 8px', flexWrap: 'wrap', marginTop: 2 }}>
        <span>{resume.date}</span>
        <span>·</span>
        <span>{resume.messages} messages</span>
        <span>·</span>
        <span>{resume.tokens.toLocaleString()} tokens</span>
        <span>·</span>
        <span>${resume.cost.toFixed(4)}</span>
        {resume.agents.length > 0 && (
          <>
            <span>·</span>
            <span>{speakerLabel(resume.agents[0])}</span>
            {resume.agents.length > 1 && (
              <span style={{ color: theme.textDisabled }}>+{resume.agents.length - 1}</span>
            )}
          </>
        )}
      </span>
      <span
        style={{
          display: 'inline-block',
          marginTop: 8,
          fontSize: 13,
          fontWeight: 600,
          color: accent,
          textDecoration: 'underline',
          textUnderlineOffset: 3,
        }}
      >
        resume →
      </span>
    </button>
  )
}
