// AgentOverviewPanel — Tools · Recent sessions · Cost 14d · Configuration.
// Lifted from AgentDetailView's body to make room for the Phase-6 tab router.

import { Cost14dSparkline } from './Cost14dSparkline'
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
  const sectionHeader = (label: string) => (
    <div
      style={{
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 10,
        letterSpacing: 1.4,
        color: theme.textDisabled,
        textTransform: 'uppercase',
        marginBottom: 10,
        marginTop: 24,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span>{label}</span>
      <span style={{ flex: 1, height: 1, background: theme.border }} />
    </div>
  )

  return (
    <>
      {sectionHeader('Tools')}
      {detail.tools.length === 0 ? (
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textDisabled,
          }}
        >
          no tools · pure reasoning agent
        </div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {detail.tools.map((t) => (
            <span
              key={t}
              style={{
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 11,
                padding: '4px 9px',
                borderRadius: 4,
                background: theme.surface2,
                color: theme.textSecondary,
                border: `1px solid ${theme.border}`,
              }}
            >
              {t}
            </span>
          ))}
        </div>
      )}

      {sectionHeader('Recent sessions')}
      {detail.recent_sessions.length === 0 ? (
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textDisabled,
          }}
        >
          no sessions yet · start one above
        </div>
      ) : (
        <div
          style={{
            background: theme.surface1,
            border: `1px solid ${theme.border}`,
            borderRadius: 6,
            overflow: 'hidden',
          }}
        >
          {detail.recent_sessions.map((s, i) => (
            <div
              key={s.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '92px 1fr 70px 70px',
                gap: 12,
                alignItems: 'center',
                padding: '10px 14px',
                borderTop: i === 0 ? 'none' : `1px solid ${theme.border}`,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 11.5,
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
              <span style={{ color: theme.cost, textAlign: 'right' }}>
                ${s.cost.toFixed(4)}
              </span>
            </div>
          ))}
        </div>
      )}

      {sectionHeader('Cost · last 14 days')}
      <Cost14dSparkline
        theme={theme}
        hue={hue}
        days={detail.cost_14d}
        total={detail.cost_14d_total}
      />

      {sectionHeader('Configuration')}
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.textSecondary,
          lineHeight: 1.7,
        }}
      >
        <div>
          model · <span style={{ color: theme.textDisabled }}>(inherits from session)</span>
        </div>
        <div>
          prompt ·{' '}
          <span style={{ color: theme.textPrimary }}>
            {detail.prompt_path ?? '(assembled from data/context/)'}
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

      {/* agentId is exposed for downstream tabs that key fetches on it. */}
      <span style={{ display: 'none' }} data-agent-id={agentId} />
    </>
  )
}
