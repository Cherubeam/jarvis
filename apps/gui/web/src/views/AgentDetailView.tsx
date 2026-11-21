// AgentDetailView — one agent's page: name, command, description, then the tab
// panels (Overview / Prompt / Includes / Versions / Stats / Context). The panels
// lay themselves out on the page grid (`.jr-row`), so this view adds no frame.

import { useEffect, useState } from 'react'

import { AgentContextPanel } from '../components/agents/AgentContextPanel'
import { AgentIncludesPanel } from '../components/agents/AgentIncludesPanel'
import { AgentOverviewPanel } from '../components/agents/AgentOverviewPanel'
import { AgentPromptPanel } from '../components/agents/AgentPromptPanel'
import { AgentStatsPanel } from '../components/agents/AgentStatsPanel'
import { AgentVersionsPanel } from '../components/agents/AgentVersionsPanel'
import {
  JournalRow,
  noteStyle,
  primaryButton,
  readStyle,
  textButton,
} from '../components/agents/journal'
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
    <div
      className="jr-pane"
      style={{ flex: 1, overflow: 'auto', minWidth: 0, background: theme.surface0 }}
    >
      <div style={{ padding: '16px 0 64px' }}>
        <JournalRow theme={theme}>
          <button
            onClick={onBack}
            style={{
              ...textButton(theme.textSecondary),
              ...noteStyle(theme.textSecondary),
              padding: '4px 0',
            }}
          >
            ← agents
          </button>
        </JournalRow>

        {loading && (
          <JournalRow theme={theme}>
            <div style={noteStyle(theme.textDisabled)}>loading…</div>
          </JournalRow>
        )}

        {error === 'not_found' && (
          <JournalRow theme={theme}>
            <div style={noteStyle(theme.error)}>agent "{agentId}" not found</div>
          </JournalRow>
        )}

        {error && error !== 'not_found' && (
          <JournalRow theme={theme}>
            <div style={noteStyle(theme.error)}>failed to load: {error}</div>
          </JournalRow>
        )}

        {detail && (
          <>
            <JournalRow theme={theme}>
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '10px 18px',
                }}
              >
                <h1
                  style={{
                    margin: 0,
                    fontFamily: JARVIS_FONTS.serif,
                    fontSize: 32,
                    fontWeight: 600,
                    lineHeight: 1.2,
                    color: theme.textPrimary,
                  }}
                >
                  {speakerLabel(agentId)}
                </h1>
                <button
                  onClick={() => onStartSession(detail.command || null)}
                  style={primaryButton(theme)}
                >
                  start session →
                </button>
              </div>
              <div
                style={{
                  ...noteStyle(theme.textSecondary),
                  marginTop: 8,
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '0 8px',
                }}
              >
                {detail.command && <span>{detail.command}</span>}
                {detail.command && <span>·</span>}
                <span>packages/agents/{agentId.toLowerCase()}/</span>
              </div>
              <p style={{ margin: '14px 0 0', ...readStyle(theme, 18), color: theme.textPrimary }}>
                {detail.description}
              </p>
              <nav
                aria-label="Agent sections"
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '4px 18px',
                  marginTop: 22,
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 13,
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
                      aria-current={active ? 'true' : undefined}
                      style={{
                        ...textButton(active ? theme.textPrimary : theme.textSecondary),
                        padding: '4px 0',
                        textDecoration: active ? 'underline' : 'none',
                        textUnderlineOffset: 4,
                      }}
                    >
                      {tab.label}
                    </button>
                  )
                })}
              </nav>
            </JournalRow>

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
