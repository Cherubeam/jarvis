// AgentsView — the directory of all registered agents, grouped by category:
// a heading per category, one row per agent.

import { useEffect, useMemo, useState } from 'react'

import { AgentCard } from '../components/agents/AgentCard'
import { CategorySection } from '../components/agents/CategorySection'
import { JournalRow, noteStyle } from '../components/agents/journal'
import { groupByCategory } from '../lib/agentCategories'
import { relativeDate } from '../lib/agentsRelativeDate'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { Agent, ConversationListResponse } from '../lib/types'

export function AgentsView({
  theme,
  accent,
  agents,
  refreshToken,
  onOpenAgent,
}: {
  theme: Theme
  accent: string
  agents: Agent[]
  refreshToken: number
  onOpenAgent: (id: string) => void
}) {
  // last_used per agent is derived from /api/conversations.
  // Re-fetched on refreshToken bumps (turn_finished) so the entries update live.
  const [lastUsed, setLastUsed] = useState<Record<string, string>>({})

  useEffect(() => {
    const ac = new AbortController()
    fetch('/api/conversations?limit=500', { signal: ac.signal })
      .then((r) => (r.ok ? (r.json() as Promise<ConversationListResponse>) : null))
      .then((data) => {
        if (!data) return
        const map: Record<string, string> = {}
        for (const conv of data.items) {
          for (const aid of conv.agents) {
            const prev = map[aid]
            if (!prev || prev < conv.date) map[aid] = conv.date
          }
        }
        setLastUsed(map)
      })
      .catch((err) => {
        if (err?.name !== 'AbortError') console.error('AgentsView /api/conversations', err)
      })
    return () => ac.abort()
  }, [refreshToken])

  const jarvis = useMemo(() => agents.find((a) => a.name === 'JARVIS'), [agents])
  const delegates = useMemo(() => agents.filter((a) => a.name !== 'JARVIS'), [agents])
  const groups = useMemo(
    () => groupByCategory(delegates.map((a) => a.name)),
    [delegates],
  )
  const byId = useMemo(() => {
    const m: Record<string, Agent> = {}
    for (const a of agents) m[a.name] = a
    return m
  }, [agents])

  return (
    <div
      className="jr-pane"
      style={{ flex: 1, overflow: 'auto', minWidth: 0, background: theme.surface0 }}
    >
      <div style={{ padding: '26px 0 64px' }}>
        <JournalRow theme={theme} margin={<>{agents.length} registered</>}>
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
            Agents
          </h1>
          <div style={{ ...noteStyle(theme.textSecondary), marginTop: 8 }}>packages/agents/</div>
        </JournalRow>

        {jarvis && (
          <CategorySection theme={theme} label="Orchestrator" featured>
            <AgentCard
              theme={theme}
              accent={accent}
              agent={jarvis}
              lastUsedLabel={relativeDate(lastUsed[jarvis.name] ?? null)}
              featured
              onClick={() => onOpenAgent(jarvis.name)}
            />
          </CategorySection>
        )}

        {groups.map((cat) => (
          <CategorySection key={cat.id} theme={theme} label={cat.label}>
            {cat.members.map((id) => {
              const agent = byId[id]
              if (!agent) return null
              return (
                <AgentCard
                  key={id}
                  theme={theme}
                  accent={accent}
                  agent={agent}
                  lastUsedLabel={relativeDate(lastUsed[id] ?? null)}
                  onClick={() => onOpenAgent(id)}
                />
              )
            })}
          </CategorySection>
        ))}

        {agents.length === 0 && (
          <JournalRow theme={theme}>
            <div style={noteStyle(theme.textDisabled)}>loading agents…</div>
          </JournalRow>
        )}
      </div>
    </div>
  )
}
