// AgentStatsPanel — char/line counts, token estimate, include resolution status.

import { Fragment, useEffect, useState } from 'react'

import type { Theme } from '../../lib/tokens'
import type { PromptIncludeRow, PromptStats } from '../../lib/types'
import { JournalRow, SectionHeading, noteStyle } from './journal'

export function AgentStatsPanel({
  theme,
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
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.error)}>failed to load stats: {error}</div>
      </JournalRow>
    )
  }
  if (!stats) {
    return (
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.textDisabled)}>loading…</div>
      </JournalRow>
    )
  }

  const row = (k: string, v: string) => (
    <Fragment key={k}>
      <dt style={{ color: theme.textSecondary }}>{k}</dt>
      <dd style={{ margin: 0, color: theme.textPrimary, overflowWrap: 'anywhere' }}>{v}</dd>
    </Fragment>
  )

  return (
    <>
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <dl
          style={{
            ...noteStyle(theme.textPrimary),
            margin: 0,
            display: 'grid',
            gridTemplateColumns: 'max-content minmax(0, 1fr)',
            gap: '6px 24px',
          }}
        >
          {row('char count', stats.char_count.toLocaleString())}
          {row('line count', stats.line_count.toLocaleString())}
          {row(
            'token estimate',
            `~${stats.token_estimate.toLocaleString()} (${stats.token_estimate_method})`,
          )}
          {row('last modified', stats.last_modified_iso ?? '—')}
          {row('snapshots on disk', stats.snapshot_count.toString())}
        </dl>
      </JournalRow>

      {stats.prompt_includes.length > 0 && (
        <JournalRow theme={theme} style={{ paddingTop: 18 }}>
          <SectionHeading theme={theme}>Prompt includes</SectionHeading>
          <div style={{ marginTop: 12 }}>
            {stats.prompt_includes.map((inc) => (
              <IncludeRow key={inc.placeholder} row={inc} theme={theme} />
            ))}
          </div>
        </JournalRow>
      )}
    </>
  )
}

function IncludeRow({ row, theme }: { row: PromptIncludeRow; theme: Theme }) {
  const bad =
    row.status === 'missing' ||
    row.status === 'found_local_example' ||
    row.status === 'found_shared_example'
  return (
    <div
      style={{
        ...noteStyle(theme.textPrimary),
        display: 'grid',
        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
        columnGap: 16,
        padding: '4px 0',
        overflowWrap: 'anywhere',
      }}
    >
      <span>{`{${row.placeholder}}`}</span>
      <span style={{ color: theme.textSecondary }}>{row.filename}.md</span>
      <span style={{ color: bad ? theme.error : theme.textSecondary }}>{row.status}</span>
    </div>
  )
}
