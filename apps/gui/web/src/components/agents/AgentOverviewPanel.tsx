// AgentOverviewPanel — Tools · Recent sessions · Cost 14d · Configuration.
// Each section is a heading with a rule and plain lines under it, in the
// reading column.

import { Cost14dSparkline } from './Cost14dSparkline'
import { JournalRow, SectionHeading, noteStyle } from './journal'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { AgentDetail } from '../../lib/types'

export function AgentOverviewPanel({
  theme,
  hue,
  agentId,
  detail,
}: {
  theme: Theme
  hue: string
  agentId: string
  detail: AgentDetail
}) {
  const sectionRow = { paddingTop: 18 }
  const body = { marginTop: 12 }

  return (
    <>
      <JournalRow theme={theme} style={sectionRow}>
        <SectionHeading theme={theme}>Tools</SectionHeading>
        {detail.tools.length === 0 ? (
          <div style={{ ...noteStyle(theme.textDisabled), ...body }}>
            no tools · pure reasoning agent
          </div>
        ) : (
          <ul
            style={{
              ...noteStyle(theme.textSecondary),
              ...body,
              marginBottom: 0,
              padding: 0,
              listStyle: 'none',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '4px 20px',
            }}
          >
            {detail.tools.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        )}
      </JournalRow>

      <JournalRow theme={theme} style={sectionRow}>
        <SectionHeading theme={theme}>Recent sessions</SectionHeading>
        {detail.recent_sessions.length === 0 ? (
          <div style={{ ...noteStyle(theme.textDisabled), ...body }}>
            no sessions yet · start one above
          </div>
        ) : (
          <div style={body}>
            {detail.recent_sessions.map((s) => (
              <div
                key={s.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '92px minmax(0, 1fr) max-content 70px',
                  columnGap: 14,
                  alignItems: 'baseline',
                  padding: '4px 0',
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 13,
                  lineHeight: 1.5,
                }}
              >
                <span style={{ color: theme.textDisabled }}>{s.date}</span>
                <span
                  style={{
                    color: theme.textPrimary,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {s.title}
                </span>
                <span style={{ color: theme.textSecondary, textAlign: 'right' }}>
                  {s.messages} msg
                </span>
                <span style={{ color: theme.textSecondary, textAlign: 'right' }}>
                  ${s.cost.toFixed(4)}
                </span>
              </div>
            ))}
          </div>
        )}
      </JournalRow>

      <JournalRow theme={theme} style={sectionRow}>
        <SectionHeading theme={theme}>Cost · last 14 days</SectionHeading>
        <div style={body}>
          <Cost14dSparkline
            theme={theme}
            hue={hue}
            days={detail.cost_14d}
            total={detail.cost_14d_total}
          />
        </div>
      </JournalRow>

      <JournalRow theme={theme} style={sectionRow}>
        <SectionHeading theme={theme}>Configuration</SectionHeading>
        <div style={{ ...noteStyle(theme.textSecondary), ...body, lineHeight: 1.7 }}>
          <div>
            model ·{' '}
            {detail.model ? (
              <span style={{ color: theme.textPrimary }}>{detail.model}</span>
            ) : (
              <span style={{ color: theme.textDisabled }}>(inherits from session)</span>
            )}
          </div>
          <div style={{ overflowWrap: 'anywhere' }}>
            prompt ·{' '}
            <span style={{ color: theme.textPrimary }}>
              {detail.prompt_path ?? '(assembled from paths.context_dir)'}
            </span>
          </div>
          <div>
            prompt includes ·{' '}
            <span style={{ color: theme.textPrimary }}>
              {detail.prompt_includes_count} file{detail.prompt_includes_count === 1 ? '' : 's'}
            </span>
          </div>
          {detail.temperature !== null && (
            <div>
              temperature ·{' '}
              <span style={{ color: theme.textPrimary }}>{detail.temperature}</span>
            </div>
          )}
          {detail.max_iterations !== null && (
            <div>
              max iterations ·{' '}
              <span style={{ color: theme.textPrimary }}>{detail.max_iterations}</span>
            </div>
          )}
          {detail.skills.length > 0 && (
            <div>
              skills · <span style={{ color: theme.textPrimary }}>{detail.skills.join(', ')}</span>
            </div>
          )}
        </div>
      </JournalRow>

      {/* agentId is exposed for downstream tabs that key fetches on it. */}
      <span style={{ display: 'none' }} data-agent-id={agentId} />
    </>
  )
}
