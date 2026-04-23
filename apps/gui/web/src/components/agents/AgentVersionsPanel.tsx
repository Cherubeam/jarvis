// AgentVersionsPanel — list of snapshots with preview + restore.

import { useEffect, useState } from 'react'

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { PromptSnapshot, PromptSnapshotDetail } from '../../lib/types'

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

  if (rows.length === 0) {
    return (
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.textDisabled,
          marginTop: 28,
        }}
      >
        no snapshots yet · save an edit to start a history
      </div>
    )
  }

  return (
    <div style={{ marginTop: 24, display: 'flex', gap: 18, alignItems: 'flex-start' }}>
      <div style={{ flex: '0 0 320px' }}>
        {error && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              color: theme.error,
              marginBottom: 10,
            }}
          >
            {error}
          </div>
        )}
        <div
          style={{
            background: theme.surface1,
            border: `1px solid ${theme.border}`,
            borderRadius: 6,
            overflow: 'hidden',
          }}
        >
          {rows.map((r, i) => {
            const active = selected?.id === r.id
            return (
              <div
                key={r.id}
                style={{
                  padding: '10px 12px',
                  borderTop: i === 0 ? 'none' : `1px solid ${theme.border}`,
                  background: active ? theme.surface2 : 'transparent',
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                  cursor: 'pointer',
                }}
                onClick={() => loadSnapshot(r.id)}
              >
                <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                  <span style={{ color: theme.textPrimary }}>{formatTs(r.timestamp)}</span>
                  <span style={{ color: kindColor(r.kind, theme, hue) }}>[{r.kind}]</span>
                  <span style={{ flex: 1 }} />
                  <span style={{ color: theme.textDisabled }}>{r.bytes}b</span>
                </div>
                {r.note && <div style={{ color: theme.textSecondary }}>{r.note}</div>}
                {active && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        restore(r.id)
                      }}
                      style={{
                        all: 'unset',
                        cursor: 'pointer',
                        padding: '4px 10px',
                        borderRadius: 3,
                        background: hue,
                        color: theme.surface0,
                        fontSize: 10,
                        fontWeight: 700,
                      }}
                    >
                      restore
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {selectedLoading && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textDisabled,
            }}
          >
            loading snapshot…
          </div>
        )}
        {!selectedLoading && selected && (
          <pre
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textPrimary,
              background: theme.surface2,
              border: `1px solid ${theme.border}`,
              borderRadius: 6,
              padding: 14,
              margin: 0,
              whiteSpace: 'pre-wrap',
              maxHeight: 520,
              overflow: 'auto',
            }}
          >
            {selected.content}
          </pre>
        )}
        {!selectedLoading && !selected && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textDisabled,
            }}
          >
            click a snapshot to preview
          </div>
        )}
      </div>
    </div>
  )
}

function kindColor(kind: PromptSnapshot['kind'], theme: Theme, hue: string): string {
  if (kind === 'pre_first_save') return theme.textDisabled
  if (kind === 'pre_restore') return theme.error
  return hue
}

function formatTs(ts: string): string {
  // Render "2026-04-23T11:53:44.123+00:00" → "2026-04-23 11:53:44".
  const m = ts.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/)
  return m ? `${m[1]} ${m[2]}` : ts
}
