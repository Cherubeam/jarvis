// AgentDetailView — hosts the 5 tab panels (Overview / Prompt / Versions / Stats / Context).
// Phase 5 shipped the Overview tab; Phase 6 activates the rest.

import { useEffect, useState } from 'react'

import { AgentContextPanel } from '../components/agents/AgentContextPanel'
import { AgentIncludesPanel } from '../components/agents/AgentIncludesPanel'
import { AgentOverviewPanel } from '../components/agents/AgentOverviewPanel'
import { AgentPromptPanel } from '../components/agents/AgentPromptPanel'
import { AgentStatsPanel } from '../components/agents/AgentStatsPanel'
import { AgentVersionsPanel } from '../components/agents/AgentVersionsPanel'
import { hueFor } from '../lib/agentHues'
import { speakerLabel } from '../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { AgentDetail } from '../lib/types'

type TabKey = 'overview' | 'prompt' | 'includes' | 'versions' | 'stats' | 'context'

const ALL_TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'prompt', label: 'Prompt' },
  { key: 'includes', label: 'Includes' },
  { key: 'versions', label: 'Versions' },
  { key: 'stats', label: 'Stats' },
  { key: 'context', label: 'Context' },
]

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
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  // Bumped after Save/Restore so Versions/Stats/Context tabs refetch.
  const [promptRefreshToken, setPromptRefreshToken] = useState(0)

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

  const bumpPromptRefresh = () => setPromptRefreshToken((t) => t + 1)

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

            <div
              style={{
                display: 'flex',
                gap: 18,
                marginTop: 22,
                borderBottom: `1px solid ${theme.border}`,
                paddingBottom: 8,
              }}
            >
              {ALL_TABS.filter(
                (t) => t.key !== 'includes' || (detail.prompt_includes_count ?? 0) > 0,
              ).map((tab) => {
                const active = tab.key === activeTab
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    style={{
                      all: 'unset',
                      cursor: 'pointer',
                      fontFamily: JARVIS_FONTS.mono,
                      fontSize: 11,
                      color: active ? theme.textPrimary : theme.textSecondary,
                      borderBottom: active ? `2px solid ${hue}` : 'none',
                      paddingBottom: 6,
                      marginBottom: -9,
                      fontWeight: active ? 600 : 400,
                    }}
                  >
                    {tab.label}
                  </button>
                )
              })}
            </div>

            {activeTab === 'overview' && (
              <AgentOverviewPanel theme={theme} hue={hue} agentId={agentId} detail={detail} />
            )}
            {activeTab === 'prompt' && (
              <AgentPromptPanel
                theme={theme}
                hue={hue}
                agentId={agentId}
                onSaved={bumpPromptRefresh}
              />
            )}
            {activeTab === 'includes' && (
              <AgentIncludesPanel
                theme={theme}
                hue={hue}
                agentId={agentId}
                refreshToken={promptRefreshToken}
                onChanged={bumpPromptRefresh}
              />
            )}
            {activeTab === 'versions' && (
              <AgentVersionsPanel
                theme={theme}
                hue={hue}
                agentId={agentId}
                refreshToken={promptRefreshToken}
                onRestored={bumpPromptRefresh}
              />
            )}
            {activeTab === 'stats' && (
              <AgentStatsPanel
                theme={theme}
                hue={hue}
                agentId={agentId}
                refreshToken={promptRefreshToken}
              />
            )}
            {activeTab === 'context' && (
              <AgentContextPanel
                theme={theme}
                hue={hue}
                agentId={agentId}
                refreshToken={promptRefreshToken}
              />
            )}
          </>
        )}
      </div>
    </div>
  )
}
