// AgentStatsPanel — char/line counts, token estimate, include resolution status.

import { useEffect, useState } from 'react'

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { PromptIncludeRow, PromptStats } from '../../lib/types'

export function AgentStatsPanel({
  theme,
  hue,
  agentId,
  refreshToken,
}: {
  theme: Theme
  hue: string
  agentId: string
  refreshToken: number
}) {
  const [stats, setStats] = useState<PromptStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const ac = new AbortController()
    setError(null)
    fetch(`/api/agents/${encodeURIComponent(agentId)}/prompt/stats`, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body: PromptStats) => setStats(body))
      .catch((e) => {
        if (e?.name !== 'AbortError') setError(e?.message || String(e))
      })
    return () => ac.abort()
  }, [agentId, refreshToken])

  if (error) {
    return (
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.error,
          marginTop: 28,
        }}
      >
        failed to load stats: {error}
      </div>
    )
  }
  if (!stats) {
    return (
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.textDisabled,
          marginTop: 28,
        }}
      >
        loading…
      </div>
    )
  }

  const row = (k: string, v: string) => (
    <div style={{ display: 'flex', gap: 12, padding: '6px 0' }} key={k}>
      <span style={{ color: theme.textDisabled, minWidth: 160 }}>{k}</span>
      <span style={{ color: theme.textPrimary }}>{v}</span>
    </div>
  )

  return (
    <div style={{ marginTop: 24, fontFamily: JARVIS_FONTS.mono, fontSize: 12 }}>
      {row('char count', stats.char_count.toLocaleString())}
      {row('line count', stats.line_count.toLocaleString())}
      {row(
        'token estimate',
        `~${stats.token_estimate.toLocaleString()} (${stats.token_estimate_method})`,
      )}
      {row('last modified', stats.last_modified_iso ?? '—')}
      {row('snapshots on disk', stats.snapshot_count.toString())}

      {stats.prompt_includes.length > 0 && (
        <>
          <div
            style={{
              marginTop: 22,
              marginBottom: 8,
              color: theme.textDisabled,
              textTransform: 'uppercase',
              letterSpacing: 1.4,
              fontSize: 10,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span>Prompt includes</span>
            <span style={{ flex: 1, height: 1, background: theme.border }} />
          </div>
          <div
            style={{
              background: theme.surface1,
              border: `1px solid ${theme.border}`,
              borderRadius: 6,
              overflow: 'hidden',
            }}
          >
            {stats.prompt_includes.map((inc, i) => (
              <IncludeRow key={inc.placeholder} row={inc} first={i === 0} theme={theme} hue={hue} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function IncludeRow({
  row,
  first,
  theme,
  hue,
}: {
  row: PromptIncludeRow
  first: boolean
  theme: Theme
  hue: string
}) {
  const bad =
    row.status === 'missing' ||
    row.status === 'found_local_example' ||
    row.status === 'found_shared_example'
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '180px 180px 1fr',
        gap: 12,
        padding: '8px 12px',
        borderTop: first ? 'none' : `1px solid ${theme.border}`,
        fontSize: 11,
      }}
    >
      <span style={{ color: theme.textPrimary }}>{`{${row.placeholder}}`}</span>
      <span style={{ color: theme.textSecondary }}>{row.filename}.md</span>
      <span style={{ color: bad ? theme.error : hue }}>{row.status}</span>
    </div>
  )
}
