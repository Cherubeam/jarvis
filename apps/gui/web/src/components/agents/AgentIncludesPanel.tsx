// AgentIncludesPanel — edit prompt-include files (Phase 6 follow-up).
// Two-pane: left list of declared includes; right editor + last-5 snapshots.
// Shared-file edits require an explicit confirm modal because they propagate
// to every agent that resolves the same filename to _shared/prompts/.

import { useEffect, useMemo, useState } from 'react'

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type {
  IncludeDetail,
  IncludeRow,
  IncludeSaveResult,
  IncludeStatus,
  PromptSnapshot,
} from '../../lib/types'

export function AgentIncludesPanel({
  theme,
  hue,
  agentId,
  refreshToken,
  onChanged,
}: {
  theme: Theme
  hue: string
  agentId: string
  refreshToken: number
  onChanged: () => void
}) {
  const [rows, setRows] = useState<IncludeRow[]>([])
  const [activePlaceholder, setActivePlaceholder] = useState<string | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [listLoading, setListLoading] = useState(true)

  useEffect(() => {
    const ac = new AbortController()
    setListLoading(true)
    setListError(null)
    fetch(`/api/agents/${encodeURIComponent(agentId)}/includes`, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body: IncludeRow[]) => {
        setRows(body)
        setListLoading(false)
        // Pin the active selection if it still exists; otherwise pick the first.
        setActivePlaceholder((prev) => {
          if (prev && body.some((r) => r.placeholder === prev)) return prev
          return body[0]?.placeholder ?? null
        })
      })
      .catch((e) => {
        if (e?.name !== 'AbortError') {
          setListError(e?.message || String(e))
          setListLoading(false)
        }
      })
    return () => ac.abort()
  }, [agentId, refreshToken])

  if (listLoading) {
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

  if (listError) {
    return (
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.error,
          marginTop: 28,
        }}
      >
        failed to load includes: {listError}
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
        no prompt_includes declared in meta.yaml
      </div>
    )
  }

  return (
    <div style={{ marginTop: 24, display: 'flex', gap: 18, alignItems: 'flex-start' }}>
      <div style={{ flex: '0 0 280px' }}>
        <div
          style={{
            background: theme.surface1,
            border: `1px solid ${theme.border}`,
            borderRadius: 6,
            overflow: 'hidden',
          }}
        >
          {rows.map((r, i) => {
            const active = r.placeholder === activePlaceholder
            return (
              <div
                key={r.placeholder}
                onClick={() => setActivePlaceholder(r.placeholder)}
                data-testid={`include-row-${r.placeholder}`}
                style={{
                  padding: '10px 12px',
                  borderTop: i === 0 ? 'none' : `1px solid ${theme.border}`,
                  background: active ? theme.surface2 : 'transparent',
                  borderLeft: active ? `2px solid ${hue}` : '2px solid transparent',
                  cursor: 'pointer',
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                }}
              >
                <div style={{ color: theme.textPrimary, fontWeight: 600 }}>{r.placeholder}</div>
                <div style={{ color: theme.textSecondary, marginTop: 2 }}>{r.filename}.md</div>
                <div style={{ marginTop: 6 }}>
                  <StatusBadge theme={theme} hue={hue} status={r.status} />
                </div>
              </div>
            )
          })}
        </div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {activePlaceholder && (
          <IncludeEditor
            key={activePlaceholder}
            theme={theme}
            hue={hue}
            agentId={agentId}
            placeholder={activePlaceholder}
            onChanged={onChanged}
          />
        )}
      </div>
    </div>
  )
}

function StatusBadge({
  theme,
  hue,
  status,
}: {
  theme: Theme
  hue: string
  status: IncludeStatus
}) {
  const { label, color } = labelFor(status, theme, hue)
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '1px 6px',
        borderRadius: 3,
        fontSize: 10,
        color,
        border: `1px solid ${color}`,
        letterSpacing: 0.3,
      }}
    >
      {label}
    </span>
  )
}

function labelFor(status: IncludeStatus, theme: Theme, hue: string): { label: string; color: string } {
  switch (status) {
    case 'found_local':
      return { label: 'local', color: hue }
    case 'found_shared':
      return { label: 'shared', color: '#5eead4' } // cyan-ish, distinct from agent hue
    case 'found_local_example':
    case 'found_shared_example':
      return { label: 'example', color: theme.textSecondary }
    case 'missing':
      return { label: 'missing', color: theme.error }
  }
}

function IncludeEditor({
  theme,
  hue,
  agentId,
  placeholder,
  onChanged,
}: {
  theme: Theme
  hue: string
  agentId: string
  placeholder: string
  onChanged: () => void
}) {
  const [data, setData] = useState<IncludeDetail | null>(null)
  const [original, setOriginal] = useState('')
  const [content, setContent] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [snapshots, setSnapshots] = useState<PromptSnapshot[]>([])
  const [confirming, setConfirming] = useState(false)
  const [refreshTick, setRefreshTick] = useState(0)

  const url = `/api/agents/${encodeURIComponent(agentId)}/includes/${encodeURIComponent(placeholder)}`

  useEffect(() => {
    const ac = new AbortController()
    setStatus('idle')
    setError(null)
    fetch(url, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body: IncludeDetail) => {
        setData(body)
        setOriginal(body.content)
        setContent(body.content)
      })
      .catch((e) => {
        if (e?.name !== 'AbortError') setError(e?.message || String(e))
      })
    return () => ac.abort()
  }, [url, refreshTick])

  useEffect(() => {
    const ac = new AbortController()
    fetch(`${url}/snapshots`, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((rows: PromptSnapshot[]) => setSnapshots(rows))
      .catch(() => {
        /* swallow — snapshots are optional UI */
      })
    return () => ac.abort()
  }, [url, refreshTick])

  const dirty = data !== null && content !== original
  const isShared = data?.status === 'found_shared'
  const isExampleOrMissing =
    data?.status === 'found_local_example' ||
    data?.status === 'found_shared_example' ||
    data?.status === 'missing'

  const promote = async () => {
    setError(null)
    try {
      const r = await fetch(`${url}/promote`, { method: 'POST' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setRefreshTick((t) => t + 1)
      onChanged()
    } catch (e) {
      setError((e as Error).message || String(e))
    }
  }

  const performSave = async () => {
    setConfirming(false)
    setStatus('saving')
    setError(null)
    try {
      const r = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const body = (await r.json()) as IncludeSaveResult
      setOriginal(content)
      setData((prev) =>
        prev ? { ...prev, bytes: body.bytes, last_modified_iso: body.last_modified_iso } : prev,
      )
      setStatus('saved')
      onChanged()
      setRefreshTick((t) => t + 1)
      window.setTimeout(() => setStatus('idle'), 1500)
    } catch (e) {
      setError((e as Error).message || String(e))
      setStatus('error')
    }
  }

  const onSaveClick = () => {
    if (!dirty) return
    if (isShared && data && data.affects_agents.length > 0) {
      setConfirming(true)
      return
    }
    void performSave()
  }

  const restore = async (snapId: string) => {
    if (!window.confirm(`Restore snapshot ${snapId}? This overwrites the current content.`)) return
    try {
      const r = await fetch(`${url}/restore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ snapshot_id: snapId }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setRefreshTick((t) => t + 1)
      onChanged()
    } catch (e) {
      setError((e as Error).message || String(e))
    }
  }

  const last5 = useMemo(() => snapshots.slice(0, 5), [snapshots])

  if (!data && !error) {
    return (
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.textDisabled,
        }}
      >
        loading include…
      </div>
    )
  }
  if (!data) {
    return (
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.error,
        }}
      >
        failed to load: {error}
      </div>
    )
  }

  return (
    <div>
      {/* Header — path + status + affects_agents hint */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 6,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color: theme.textSecondary,
        }}
      >
        <span data-testid="include-path" style={{ color: theme.textDisabled }}>
          {data.path ?? '(unresolved)'}
        </span>
        <span style={{ flex: 1 }} />
        {status === 'saved' && <span style={{ color: hue }}>saved ✓</span>}
        {status === 'error' && <span style={{ color: theme.error }}>error: {error}</span>}
        {dirty && !isExampleOrMissing && (
          <button
            onClick={() => setContent(original)}
            style={revertBtnStyle(theme)}
          >
            revert
          </button>
        )}
        {!isExampleOrMissing && (
          <button
            onClick={onSaveClick}
            disabled={!dirty || status === 'saving'}
            style={saveBtnStyle(theme, hue, dirty, status === 'saving')}
          >
            {status === 'saving' ? 'saving…' : 'save'}
          </button>
        )}
      </div>

      {/* Shared-file warning bar */}
      {isShared && data.affects_agents.length > 0 && (
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: theme.textSecondary,
            background: theme.surface2,
            border: `1px solid ${theme.border}`,
            borderRadius: 4,
            padding: '6px 10px',
            marginBottom: 10,
          }}
        >
          editing this shared file also affects: {data.affects_agents.join(', ')}
        </div>
      )}

      {/* Promote prompt */}
      {isExampleOrMissing && (
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: theme.textSecondary,
            background: theme.surface1,
            border: `1px solid ${theme.border}`,
            borderRadius: 4,
            padding: '10px 12px',
            marginBottom: 10,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <span style={{ flex: 1 }}>
            {data.status === 'missing'
              ? 'no file backs this include — promote to create a local override.'
              : 'this resolves to a starter template — promote to make a local copy you can edit.'}
          </span>
          <button onClick={promote} style={promoteBtnStyle(theme, hue)}>
            promote to local
          </button>
        </div>
      )}

      <textarea
        value={content}
        readOnly={isExampleOrMissing}
        onChange={(e) => setContent(e.target.value)}
        spellCheck={false}
        rows={22}
        style={{
          width: '100%',
          boxSizing: 'border-box',
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
          lineHeight: 1.55,
          padding: 14,
          color: isExampleOrMissing ? theme.textDisabled : theme.textPrimary,
          background: theme.surface1,
          border: `1px solid ${dirty && !isExampleOrMissing ? hue : theme.border}`,
          borderRadius: 6,
          resize: 'vertical',
          outline: 'none',
        }}
      />
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 10,
          color: theme.textDisabled,
          marginTop: 6,
        }}
      >
        changes take effect on the next session · {content.length.toLocaleString()} chars
      </div>

      {/* Snapshots strip */}
      <div style={{ marginTop: 18 }}>
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 10,
            color: theme.textSecondary,
            marginBottom: 6,
            letterSpacing: 0.3,
          }}
        >
          recent snapshots
          {isShared && data.affects_agents.length > 0 && (
            <span style={{ color: theme.textDisabled }}>
              {' '}· edits made through this agent · other agents may have edited this shared file independently
            </span>
          )}
        </div>
        {last5.length === 0 ? (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              color: theme.textDisabled,
            }}
          >
            no snapshots yet · save an edit to start a history
          </div>
        ) : (
          <div
            style={{
              background: theme.surface1,
              border: `1px solid ${theme.border}`,
              borderRadius: 4,
              overflow: 'hidden',
            }}
          >
            {last5.map((s, i) => (
              <div
                key={s.id}
                style={{
                  padding: '6px 10px',
                  borderTop: i === 0 ? 'none' : `1px solid ${theme.border}`,
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                  display: 'flex',
                  gap: 10,
                  alignItems: 'center',
                }}
              >
                <span style={{ color: theme.textPrimary }}>{formatTs(s.timestamp)}</span>
                <span style={{ color: kindColor(s.kind, theme, hue) }}>[{s.kind}]</span>
                <span style={{ color: theme.textDisabled }}>{s.bytes}b</span>
                <span style={{ flex: 1 }} />
                <button
                  onClick={() => restore(s.id)}
                  style={{
                    all: 'unset',
                    cursor: 'pointer',
                    padding: '3px 9px',
                    borderRadius: 3,
                    border: `1px solid ${theme.border}`,
                    color: theme.textSecondary,
                    fontSize: 10,
                  }}
                >
                  restore
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Shared-write confirm modal */}
      {confirming && (
        <ConfirmModal
          theme={theme}
          hue={hue}
          affects={data.affects_agents}
          filename={`${data.filename}.md`}
          onCancel={() => setConfirming(false)}
          onConfirm={performSave}
        />
      )}
    </div>
  )
}

function ConfirmModal({
  theme,
  hue,
  affects,
  filename,
  onCancel,
  onConfirm,
}: {
  theme: Theme
  hue: string
  affects: string[]
  filename: string
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        data-testid="shared-confirm-modal"
        style={{
          background: theme.surface1,
          border: `1px solid ${theme.border}`,
          borderRadius: 6,
          padding: '20px 22px',
          maxWidth: 480,
          fontFamily: JARVIS_FONTS.mono,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600, color: theme.textPrimary, marginBottom: 8 }}>
          edit shared file?
        </div>
        <div style={{ fontSize: 12, color: theme.textSecondary, lineHeight: 1.55, marginBottom: 14 }}>
          <code style={{ color: theme.textPrimary }}>{filename}</code> is shared. This save also
          affects: <strong style={{ color: theme.textPrimary }}>{affects.join(', ')}</strong>.
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={revertBtnStyle(theme)}>
            cancel
          </button>
          <button onClick={onConfirm} style={saveBtnStyle(theme, hue, true, false)}>
            edit shared file
          </button>
        </div>
      </div>
    </div>
  )
}

function revertBtnStyle(theme: Theme): React.CSSProperties {
  return {
    all: 'unset',
    cursor: 'pointer',
    padding: '6px 12px',
    borderRadius: 4,
    border: `1px solid ${theme.border}`,
    color: theme.textSecondary,
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 11,
  }
}

function saveBtnStyle(
  theme: Theme,
  hue: string,
  dirty: boolean,
  saving: boolean,
): React.CSSProperties {
  return {
    all: 'unset',
    cursor: dirty && !saving ? 'pointer' : 'not-allowed',
    padding: '6px 14px',
    borderRadius: 4,
    background: dirty ? hue : theme.surface2,
    color: dirty ? theme.surface0 : theme.textDisabled,
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 0.3,
  }
}

function promoteBtnStyle(theme: Theme, hue: string): React.CSSProperties {
  return {
    all: 'unset',
    cursor: 'pointer',
    padding: '5px 12px',
    borderRadius: 4,
    background: hue,
    color: theme.surface0,
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: 0.3,
  }
}

function kindColor(kind: PromptSnapshot['kind'], theme: Theme, hue: string): string {
  if (kind === 'pre_first_save') return theme.textDisabled
  if (kind === 'pre_restore') return theme.error
  return hue
}

function formatTs(ts: string): string {
  const m = ts.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/)
  return m ? `${m[1]} ${m[2]}` : ts
}
