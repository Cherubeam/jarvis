// HistoryView — replaces the Phase-1 Stub for the 'history' left-rail route.
// Two-pane: 400px filters + date-bucketed list, flex detail pane.

import { useEffect, useMemo, useState } from 'react'

import { ConvDetailPane } from '../components/history/ConvDetailPane'
import { ConvFilters } from '../components/history/ConvFilters'
import { ConvList } from '../components/history/ConvList'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type {
  ConversationListResponse,
  ConversationSummary,
  DatePreset,
  HistoryFacets,
  SortMode,
} from '../lib/types'

export function HistoryView({
  theme,
  accent,
  refreshToken,
  selectedId,
  setSelectedId,
  onResume,
  onConversationDeleted,
}: {
  theme: Theme
  accent: string
  /** Bumped by App on turn_finished so the view re-fetches without reload. */
  refreshToken: number
  selectedId: string | null
  setSelectedId: (id: string | null) => void
  /** Switch to chat and queue a resume for the given file_id. */
  onResume: (fileId: string) => void
  /** Called after a successful DELETE so App can bump the global refresh token. */
  onConversationDeleted: (id: string) => void
}) {
  const [all, setAll] = useState<ConversationSummary[]>([])
  const [facets, setFacets] = useState<HistoryFacets>({ agents: [], tools: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [query, setQuery] = useState('')
  const [agentFilter, setAgentFilter] = useState('all')
  const [toolFilter, setToolFilter] = useState('all')
  const [datePreset, setDatePreset] = useState<DatePreset>('all')
  const [sortMode, setSortMode] = useState<SortMode>('recent')

  // Fetch the list (non-search filters are server-side); search is client-side.
  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ limit: '200', sort: sortMode })
    if (agentFilter !== 'all') params.set('agent', agentFilter)
    if (toolFilter !== 'all') params.set('tool', toolFilter)
    if (datePreset !== 'all') params.set('date', datePreset)

    const ac = new AbortController()
    fetch(`/api/conversations?${params.toString()}`, { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<ConversationListResponse>
      })
      .then((data) => {
        setAll(data.items)
        setLoading(false)
      })
      .catch((e) => {
        if (e.name === 'AbortError') return
        setError(String(e.message || e))
        setLoading(false)
      })
    return () => ac.abort()
  }, [agentFilter, toolFilter, datePreset, sortMode, refreshToken])

  // Facets — load once per mount, plus on refreshToken so turn_finished updates them.
  useEffect(() => {
    const ac = new AbortController()
    fetch('/api/conversations/facets', { signal: ac.signal })
      .then((r) => r.json() as Promise<HistoryFacets>)
      .then(setFacets)
      .catch(() => {
        /* non-fatal */
      })
    return () => ac.abort()
  }, [refreshToken])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return all
    return all.filter((c) => c.title.toLowerCase().includes(q))
  }, [all, query])

  // Keep a valid selection as filters change.
  useEffect(() => {
    if (filtered.length === 0) return
    if (!selectedId || !filtered.find((c) => c.id === selectedId)) {
      setSelectedId(filtered[0].id)
    }
  }, [filtered, selectedId, setSelectedId])

  const selected = filtered.find((c) => c.id === selectedId) || null

  const totalCost = filtered.reduce((s, c) => s + c.cost, 0)
  const totalMessages = filtered.reduce((s, c) => s + c.messages, 0)
  const totalTokens = filtered.reduce((s, c) => s + c.tokens, 0)

  const activeFilterCount =
    (query ? 1 : 0) +
    (agentFilter !== 'all' ? 1 : 0) +
    (toolFilter !== 'all' ? 1 : 0) +
    (datePreset !== 'all' ? 1 : 0)

  const clearFilters = () => {
    setQuery('')
    setAgentFilter('all')
    setToolFilter('all')
    setDatePreset('all')
  }

  return (
    <main
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        background: theme.surface0,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          flexShrink: 0,
          padding: '20px 28px 16px',
          borderBottom: `1px solid ${theme.border}`,
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          gap: '4px 18px',
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
          History
        </h1>
        <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.textSecondary }}>
          {loading ? (
            <span style={{ color: theme.textDisabled }}>loading…</span>
          ) : error ? (
            <span style={{ color: theme.error }}>failed: {error}</span>
          ) : (
            <>
              {filtered.length} of {facets.total}
              <span style={{ color: theme.stats }}>
                {' '}
                · {totalMessages} msg · {totalTokens.toLocaleString()} tok ·{' '}
              </span>
              <span>${totalCost.toFixed(4)}</span>
            </>
          )}
        </div>
        <div
          style={{
            marginLeft: 'auto',
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textDisabled,
          }}
        >
          ~/jarvis/data/conversations/
        </div>
      </div>

      {/* Two panes on one surface, told apart by a single rule. */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
        <div
          style={{
            width: 400,
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            borderRight: `1px solid ${theme.border}`,
          }}
        >
          <ConvFilters
            theme={theme}
            accent={accent}
            query={query}
            setQuery={setQuery}
            agentFilter={agentFilter}
            setAgentFilter={setAgentFilter}
            toolFilter={toolFilter}
            setToolFilter={setToolFilter}
            datePreset={datePreset}
            setDatePreset={setDatePreset}
            sortMode={sortMode}
            setSortMode={setSortMode}
            activeFilterCount={activeFilterCount}
            clearFilters={clearFilters}
            agents={facets.agents}
            tools={facets.tools}
          />
          <ConvList
            theme={theme}
            accent={accent}
            conversations={filtered}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>
        <ConvDetailPane
          theme={theme}
          accent={accent}
          conversation={selected}
          onResume={onResume}
          onDeleted={(id) => {
            setAll((prev) => prev.filter((c) => c.id !== id))
            if (selectedId === id) setSelectedId(null)
            onConversationDeleted(id)
          }}
        />
      </div>
    </main>
  )
}
