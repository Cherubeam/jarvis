// AgentDetailView — Overview tab of the Agent Detail page.
// Ported from JARVIS GUI v6 line 1866 (AgentDetail). Dropped the expandable
// system-prompt viewer and context-file list; those land with the Prompt
// Editor phase.

import { useEffect, useState } from 'react'

import { Cost14dSparkline } from '../components/agents/Cost14dSparkline'
import { hueFor } from '../lib/agentHues'
import { speakerLabel } from '../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { AgentDetail } from '../lib/types'

const PLACEHOLDER_TABS = ['Overview', 'Prompt', 'Versions', 'Stats', 'Context']

export function AgentDetailView({
  theme,
  accent,
  agentId,
  refreshToken,
  onBack,
  onStartSession,
}: {
  theme: Theme
  accent: string
  agentId: string
  refreshToken: number
  onBack: () => void
  onStartSession: (cmd: string | null) => void
}) {
  const [detail, setDetail] = useState<AgentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setDetail(null)
    const ac = new AbortController()
    fetch(`/api/agents/${encodeURIComponent(agentId)}`, { signal: ac.signal })
      .then((r) => {
        if (r.status === 404) throw new Error('not_found')
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<AgentDetail>
      })
      .then((d) => {
        setDetail(d)
        setLoading(false)
      })
      .catch((e) => {
        if (e?.name === 'AbortError') return
        setError(e?.message || String(e))
        setLoading(false)
      })
    return () => ac.abort()
  }, [agentId, refreshToken])

  const hue = hueFor(agentId, accent)

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
    <div style={{ flex: 1, overflow: 'auto', minWidth: 0, background: theme.surface0 }}>
      <div style={{ maxWidth: 840, margin: '0 auto', padding: '32px 48px 64px' }}>
        <button
          onClick={onBack}
          style={{
            all: 'unset',
            cursor: 'pointer',
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: theme.textSecondary,
            marginBottom: 20,
            display: 'inline-block',
          }}
        >
          ← agents
        </button>

        {loading && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textDisabled,
            }}
          >
            loading…
          </div>
        )}

        {error === 'not_found' && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.error,
            }}
          >
            agent "{agentId}" not found
          </div>
        )}

        {error && error !== 'not_found' && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.error,
            }}
          >
            failed to load: {error}
          </div>
        )}

        {detail && (
          <>
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 16,
                marginBottom: 14,
              }}
            >
              <div
                style={{
                  width: 4,
                  height: 56,
                  background: hue,
                  borderRadius: 2,
                  flexShrink: 0,
                }}
              />
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontFamily: JARVIS_FONTS.sans,
                    fontSize: 28,
                    fontWeight: 600,
                    color: theme.textPrimary,
                    letterSpacing: -0.4,
                    lineHeight: 1.1,
                  }}
                >
                  {speakerLabel(agentId)}
                </div>
                <div
                  style={{
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 12,
                    color: theme.textSecondary,
                    marginTop: 6,
                    display: 'flex',
                    gap: 8,
                  }}
                >
                  {detail.command && <span style={{ color: hue }}>{detail.command}</span>}
                  {detail.command && <span>·</span>}
                  <span>packages/agents/{agentId.toLowerCase()}/</span>
                </div>
              </div>
              <button
                onClick={() => onStartSession(detail.command || null)}
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  padding: '10px 18px',
                  borderRadius: 6,
                  background: hue,
                  color: theme.surface0,
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 12,
                  fontWeight: 700,
                  letterSpacing: 0.3,
                }}
              >
                start session →
              </button>
            </div>

            <div
              style={{
                fontSize: 15,
                color: theme.textPrimary,
                lineHeight: 1.55,
                marginTop: 4,
              }}
            >
              {detail.description}
            </div>

            {/* Placeholder tab row — sets expectation for the Prompt Editor phase. */}
            <div
              style={{
                display: 'flex',
                gap: 18,
                marginTop: 22,
                borderBottom: `1px solid ${theme.border}`,
                paddingBottom: 8,
              }}
            >
              {PLACEHOLDER_TABS.map((tab, i) => (
                <div
                  key={tab}
                  style={{
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 11,
                    color: i === 0 ? theme.textPrimary : theme.textDisabled,
                    borderBottom: i === 0 ? `2px solid ${hue}` : 'none',
                    paddingBottom: 6,
                    marginBottom: -9,
                    fontWeight: i === 0 ? 600 : 400,
                  }}
                >
                  {tab}
                </div>
              ))}
            </div>

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
                model ·{' '}
                <span style={{ color: theme.textDisabled }}>(inherits from session)</span>
              </div>
              <div>
                prompt ·{' '}
                <span style={{ color: theme.textPrimary }}>
                  {detail.prompt_path ?? '(assembled from ~/.jarvis/context/)'}
                </span>
              </div>
              <div>
                prompt includes ·{' '}
                <span style={{ color: theme.textPrimary }}>
                  {detail.prompt_includes_count} file
                  {detail.prompt_includes_count === 1 ? '' : 's'}
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
                  skills ·{' '}
                  <span style={{ color: theme.textPrimary }}>{detail.skills.join(', ')}</span>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
