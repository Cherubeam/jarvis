// ConvFilters — search + sort + date + agent + tool filters. Each filter is a
// journal row: its name in the gutter, the choices as plain text links, the
// chosen one underlined.

import type { CSSProperties } from 'react'

import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { DatePreset, FacetEntry, SortMode } from '../../lib/types'

const DATE_PRESETS: { id: DatePreset; label: string }[] = [
  { id: 'all', label: 'All time' },
  { id: '7d', label: 'Past week' },
  { id: '30d', label: 'Past month' },
  { id: 'today', label: 'Today' },
]

const SORT_MODES: { id: SortMode; label: string }[] = [
  { id: 'recent', label: 'Recent' },
  { id: 'cost', label: 'Cost' },
  { id: 'messages', label: 'Length' },
]

export function ConvFilters({
  theme,
  accent,
  query,
  setQuery,
  agentFilter,
  setAgentFilter,
  toolFilter,
  setToolFilter,
  datePreset,
  setDatePreset,
  sortMode,
  setSortMode,
  activeFilterCount,
  clearFilters,
  agents,
  tools,
}: {
  theme: Theme
  accent: string
  query: string
  setQuery: (v: string) => void
  agentFilter: string
  setAgentFilter: (v: string) => void
  toolFilter: string
  setToolFilter: (v: string) => void
  datePreset: DatePreset
  setDatePreset: (v: DatePreset) => void
  sortMode: SortMode
  setSortMode: (v: SortMode) => void
  activeFilterCount: number
  clearFilters: () => void
  agents: FacetEntry[]
  tools: FacetEntry[]
}) {
  const sectionLabel = (label: string) => (
    <div
      className="jr-gutter"
      style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.textDisabled }}
    >
      {label}
    </div>
  )

  const links: CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'baseline',
    gap: '2px 14px',
    minWidth: 0,
  }

  const chip = (active: boolean, onClick: () => void, label: string) => (
    <button
      key={label}
      onClick={onClick}
      aria-pressed={active}
      style={{
        all: 'unset',
        cursor: 'pointer',
        padding: '2px 0',
        maxWidth: '100%',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 13,
        color: active ? theme.textPrimary : theme.textSecondary,
        textDecoration: active ? 'underline' : 'none',
        textUnderlineOffset: 4,
      }}
    >
      {label}
    </button>
  )

  return (
    <div
      className="jr-pane"
      style={{
        padding: '10px 0 8px',
        borderBottom: `1px solid ${theme.border}`,
        flexShrink: 0,
      }}
    >
      <div className="jr-row dense">
        <div className="jr-gutter" />
        <div style={{ position: 'relative', minWidth: 0 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="search title…"
            aria-label="search title"
            style={{
              boxSizing: 'border-box',
              display: 'block',
              width: '100%',
              minHeight: 36,
              margin: 0,
              padding: '0 34px 0 10px',
              border: `1px solid ${theme.border}`,
              borderRadius: 4,
              background: theme.surface2,
              color: theme.textPrimary,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
            }}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              aria-label="clear search"
              style={{
                all: 'unset',
                cursor: 'pointer',
                position: 'absolute',
                top: 0,
                right: 0,
                width: 34,
                height: '100%',
                textAlign: 'center',
                lineHeight: '36px',
                color: theme.textSecondary,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 13,
              }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="jr-row dense">
        {sectionLabel('Sort')}
        <div style={links}>
          {SORT_MODES.map((s) => chip(sortMode === s.id, () => setSortMode(s.id), s.label))}
          {activeFilterCount > 0 && (
            <button
              onClick={clearFilters}
              style={{
                all: 'unset',
                cursor: 'pointer',
                marginLeft: 'auto',
                padding: '2px 0',
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 13,
                color: accent,
              }}
            >
              clear ({activeFilterCount})
            </button>
          )}
        </div>
      </div>

      <div className="jr-row dense">
        {sectionLabel('Date')}
        <div style={links}>
          {DATE_PRESETS.map((p) =>
            chip(datePreset === p.id, () => setDatePreset(p.id), p.label),
          )}
        </div>
      </div>

      <div className="jr-row dense">
        {sectionLabel('Agent')}
        <div style={links}>
          {chip(agentFilter === 'all', () => setAgentFilter('all'), 'All')}
          {agents.map((a) =>
            chip(agentFilter === a.id, () => setAgentFilter(a.id), speakerLabel(a.id)),
          )}
        </div>
      </div>

      {tools.length > 0 && (
        <div className="jr-row dense">
          {sectionLabel('Tool')}
          <div style={links}>
            {chip(toolFilter === 'all', () => setToolFilter('all'), 'All')}
            {tools.map((t) => chip(toolFilter === t.id, () => setToolFilter(t.id), t.id))}
          </div>
        </div>
      )}
    </div>
  )
}
