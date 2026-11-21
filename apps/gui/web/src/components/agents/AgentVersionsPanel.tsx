// AgentVersionsPanel — list of snapshots with preview + restore. The list and
// the preview sit side by side across the full width and stack when it is narrow.

import { useEffect, useState } from 'react'

import type { Theme } from '../../lib/tokens'
import type { PromptSnapshot, PromptSnapshotDetail } from '../../lib/types'
import { JournalRow, noteStyle, previewStyle, secondaryButton, textButton } from './journal'

export function AgentVersionsPanel({
  theme,
  hue,
  agentId,
  refreshToken,
  onRestored,
}: {
  theme: Theme
  hue: string
  agentId: string
  refreshToken: number
  onRestored: () => void
}) {
  const [rows, setRows] = useState<PromptSnapshot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<PromptSnapshotDetail | null>(null)
  const [selectedLoading, setSelectedLoading] = useState(false)

  useEffect(() => {
    const ac = new AbortController()
    setLoading(true)
    setError(null)
    fetch(`/api/agents/${encodeURIComponent(agentId)}/prompt/snapshots`, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body: PromptSnapshot[]) => {
        setRows(body)
        setLoading(false)
        // Keep the currently-selected snapshot pinned if it still exists.
        setSelected((prev) => (prev && body.some((r) => r.id === prev.id) ? prev : null))
      })
      .catch((e) => {
        if (e?.name !== 'AbortError') {
          setError(e?.message || String(e))
          setLoading(false)
        }
      })
    return () => ac.abort()
  }, [agentId, refreshToken])

  const loadSnapshot = async (id: string) => {
    setSelectedLoading(true)
    try {
      const r = await fetch(`/api/agents/${encodeURIComponent(agentId)}/prompt/snapshots/${id}`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setSelected((await r.json()) as PromptSnapshotDetail)
    } catch (e) {
      setError((e as Error).message || String(e))
    } finally {
      setSelectedLoading(false)
    }
  }

  const restore = async (id: string) => {
    if (!window.confirm(`Restore snapshot ${id}? This will overwrite the current prompt.`)) return
    try {
      const r = await fetch(`/api/agents/${encodeURIComponent(agentId)}/prompt/restore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ snapshot_id: id }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      onRestored()
    } catch (e) {
      setError((e as Error).message || String(e))
    }
  }

  if (loading) {
    return (
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.textDisabled)}>loading…</div>
      </JournalRow>
    )
  }

  if (rows.length === 0) {
    return (
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.textDisabled)}>
          no snapshots yet · save an edit to start a history
        </div>
      </JournalRow>
    )
  }

  return (
    <JournalRow theme={theme} wide style={{ paddingTop: 18 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px 28px', alignItems: 'flex-start' }}>
        <div style={{ flex: '0 1 300px', minWidth: 0 }}>
          {error && <div style={{ ...noteStyle(theme.error), marginBottom: 10 }}>{error}</div>}
          {rows.map((r, i) => {
            const active = selected?.id === r.id
            return (
              <div
                key={r.id}
                style={{
                  ...noteStyle(theme.textSecondary),
                  padding: '8px 0',
                  borderTop: i === 0 ? 'none' : `1px solid ${theme.border}`,
                }}
              >
                <button
                  onClick={() => loadSnapshot(r.id)}
                  aria-current={active ? 'true' : undefined}
                  style={{ ...textButton(theme.textSecondary), display: 'block', width: '100%' }}
                >
                  <span style={{ display: 'flex', flexWrap: 'wrap', gap: '0 8px', alignItems: 'baseline' }}>
                    <span
                      style={{
                        color: active ? hue : theme.textPrimary,
                        textDecoration: active ? 'underline' : 'none',
                        textUnderlineOffset: 4,
                      }}
                    >
                      {formatTs(r.timestamp)}
                    </span>
                    <span>[{r.kind}]</span>
                    <span style={{ flex: 1 }} />
                    <span style={{ color: theme.textDisabled }}>{r.bytes}b</span>
                  </span>
                  {r.note && <span style={{ display: 'block', marginTop: 2 }}>{r.note}</span>}
                </button>
                {active && (
                  <div style={{ marginTop: 8 }}>
                    <button onClick={() => restore(r.id)} style={secondaryButton(theme, true)}>
                      restore
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
        <div style={{ flex: '1 1 360px', minWidth: 0, paddingTop: 8 }}>
          {selectedLoading && <div style={noteStyle(theme.textDisabled)}>loading snapshot…</div>}
          {!selectedLoading && selected && (
            <pre style={previewStyle(theme, 520)}>{selected.content}</pre>
          )}
          {!selectedLoading && !selected && (
            <div style={noteStyle(theme.textDisabled)}>click a snapshot to preview</div>
          )}
        </div>
      </div>
    </JournalRow>
  )
}

function formatTs(ts: string): string {
  // Render "2026-04-23T11:53:44.123+00:00" → "2026-04-23 11:53:44".
  const m = ts.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/)
  return m ? `${m[1]} ${m[2]}` : ts
}
