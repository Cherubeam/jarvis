// ConvFilters — search + sort + date + agent chips + tool chips.
// Ported from JARVIS GUI.html 3108-3214.

import { Icon } from '../Icon'
import { hueFor } from '../../lib/agentHues'
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
      style={{
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 9.5,
        letterSpacing: 1.3,
        color: theme.textDisabled,
        textTransform: 'uppercase',
        marginBottom: 6,
        marginTop: 14,
      }}
    >
      {label}
    </div>
  )

  const chip = (
    active: boolean,
    onClick: () => void,
    label: string,
    color?: string,
  ) => (
    <button
      key={label}
      onClick={onClick}
      style={{
        all: 'unset',
        cursor: 'pointer',
        padding: '4px 10px',
        borderRadius: 4,
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 11,
        border: `1px solid ${active ? color || accent : theme.border}`,
        background: active ? `${color || accent}22` : 'transparent',
        color: active ? color || accent : theme.textSecondary,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </button>
  )

  return (
    <div
      style={{
        padding: '14px 16px 10px',
        borderBottom: `1px solid ${theme.border}`,
        flexShrink: 0,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '7px 10px',
          borderRadius: 6,
          border: `1px solid ${theme.border}`,
          background: theme.surface0,
        }}
      >
        <Icon name="search" size={13} color={theme.textDisabled} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="search title…"
          style={{
            all: 'unset',
            flex: 1,
            minWidth: 0,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textPrimary,
          }}
        />
        {query && (
          <button
            onClick={() => setQuery('')}
            style={{
              all: 'unset',
              cursor: 'pointer',
              color: theme.textDisabled,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
            }}
          >
            ✕
          </button>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 12 }}>
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 9.5,
            letterSpacing: 1.3,
            color: theme.textDisabled,
            textTransform: 'uppercase',
          }}
        >
          Sort
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {SORT_MODES.map((s) => (
            <button
              key={s.id}
              onClick={() => setSortMode(s.id)}
              style={{
                all: 'unset',
                cursor: 'pointer',
                padding: '3px 8px',
                borderRadius: 3,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 10.5,
                background: sortMode === s.id ? theme.surface2 : 'transparent',
                color: sortMode === s.id ? theme.textPrimary : theme.textSecondary,
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
        {activeFilterCount > 0 && (
          <button
            onClick={clearFilters}
            style={{
              all: 'unset',
              cursor: 'pointer',
              marginLeft: 'auto',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 10.5,
              color: accent,
            }}
          >
            clear ({activeFilterCount})
          </button>
        )}
      </div>

      {sectionLabel('Date')}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {DATE_PRESETS.map((p) =>
          chip(datePreset === p.id, () => setDatePreset(p.id), p.label),
        )}
      </div>

      {sectionLabel('Agent')}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {chip(agentFilter === 'all', () => setAgentFilter('all'), 'All')}
        {agents.map((a) => {
          const hue = hueFor(a.id, accent)
          return chip(
            agentFilter === a.id,
            () => setAgentFilter(a.id),
            speakerLabel(a.id),
            hue,
          )
        })}
      </div>

      {tools.length > 0 && (
        <>
          {sectionLabel('Tool')}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {chip(toolFilter === 'all', () => setToolFilter('all'), 'All')}
            {tools.map((t) =>
              chip(toolFilter === t.id, () => setToolFilter(t.id), t.id, theme.tool),
            )}
          </div>
        </>
      )}
    </div>
  )
}
