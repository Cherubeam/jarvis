// AgentIncludesPanel — edit prompt-include files (Phase 6 follow-up).
// Two-pane: left list of declared includes; right editor + last-5 snapshots
// (the panes stack when the page is narrow).
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
import {
  JournalRow,
  fieldStyle,
  noteStyle,
  primaryButton,
  readStyle,
  secondaryButton,
  textButton,
} from './journal'

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
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.textDisabled)}>loading…</div>
      </JournalRow>
    )
  }

  if (listError) {
    return (
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.error)}>failed to load includes: {listError}</div>
      </JournalRow>
    )
  }

  if (rows.length === 0) {
    return (
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.textDisabled)}>no prompt_includes declared in meta.yaml</div>
      </JournalRow>
    )
  }

  return (
    <JournalRow theme={theme} wide style={{ paddingTop: 18 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px 28px', alignItems: 'flex-start' }}>
        <div style={{ flex: '0 1 220px', minWidth: 0 }}>
          {rows.map((r, i) => {
            const active = r.placeholder === activePlaceholder
            return (
              <div
                key={r.placeholder}
                style={{ borderTop: i === 0 ? 'none' : `1px solid ${theme.border}` }}
              >
                <button
                  onClick={() => setActivePlaceholder(r.placeholder)}
                  data-testid={`include-row-${r.placeholder}`}
                  aria-current={active ? 'true' : undefined}
                  style={{
                    ...textButton(theme.textSecondary),
                    ...noteStyle(theme.textSecondary),
                    display: 'block',
                    width: '100%',
                    padding: '8px 0',
                    overflowWrap: 'anywhere',
                  }}
                >
                  <span
                    style={{
                      display: 'block',
                      fontWeight: 600,
                      color: active ? hue : theme.textPrimary,
                      textDecoration: active ? 'underline' : 'none',
                      textUnderlineOffset: 4,
                    }}
                  >
                    {r.placeholder}
                  </span>
                  <span style={{ display: 'block' }}>{r.filename}.md</span>
                  <span style={{ display: 'block' }}>
                    <StatusBadge theme={theme} status={r.status} />
                  </span>
                </button>
              </div>
            )
          })}
        </div>
        <div style={{ flex: '1 1 400px', minWidth: 0 }}>
          {activePlaceholder && (
            <IncludeEditor
              key={activePlaceholder}
              theme={theme}
              agentId={agentId}
              placeholder={activePlaceholder}
              onChanged={onChanged}
            />
          )}
        </div>
      </div>
    </JournalRow>
  )
}

/** Where an include resolves to, as plain text. Only a missing file is flagged. */
function StatusBadge({ theme, status }: { theme: Theme; status: IncludeStatus }) {
  const { label, color } = labelFor(status, theme)
  return <span style={{ fontSize: 12, color }}>{label}</span>
}

function labelFor(status: IncludeStatus, theme: Theme): { label: string; color: string } {
  switch (status) {
    case 'found_local':
      return { label: 'local', color: theme.textDisabled }
    case 'found_shared':
      return { label: 'shared', color: theme.textDisabled }
    case 'found_local_example':
    case 'found_shared_example':
      return { label: 'example', color: theme.textDisabled }
    case 'missing':
      return { label: 'missing', color: theme.error }
  }
}

function IncludeEditor({
  theme,
  agentId,
  placeholder,
  onChanged,
}: {
  theme: Theme
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
    return <div style={noteStyle(theme.textDisabled)}>loading include…</div>
  }
  if (!data) {
    return <div style={noteStyle(theme.error)}>failed to load: {error}</div>
  }

  const canSave = dirty && status !== 'saving'

  return (
    <div>
      {/* Header — path + status + affects_agents hint */}
      <div
        style={{
          ...noteStyle(theme.textSecondary),
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 10,
          marginBottom: 10,
        }}
      >
        <span
          data-testid="include-path"
          style={{ color: theme.textDisabled, overflowWrap: 'anywhere' }}
        >
          {data.path ?? '(unresolved)'}
        </span>
        <span style={{ flex: 1 }} />
        {status === 'saved' && <span>saved ✓</span>}
        {status === 'error' && <span style={{ color: theme.error }}>error: {error}</span>}
        {dirty && !isExampleOrMissing && (
          <button onClick={() => setContent(original)} style={secondaryButton(theme)}>
            revert
          </button>
        )}
        {!isExampleOrMissing && (
          <button onClick={onSaveClick} disabled={!canSave} style={primaryButton(theme, canSave)}>
            {status === 'saving' ? 'saving…' : 'save'}
          </button>
        )}
      </div>

      {/* Shared-file warning */}
      {isShared && data.affects_agents.length > 0 && (
        <div style={{ ...noteStyle(theme.textPrimary), marginBottom: 10 }}>
          editing this shared file also affects: {data.affects_agents.join(', ')}
        </div>
      )}

      {/* Promote prompt */}
      {isExampleOrMissing && (
        <div
          style={{
            ...noteStyle(theme.textSecondary),
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 12,
            marginBottom: 10,
          }}
        >
          <span style={{ flex: '1 1 260px' }}>
            {data.status === 'missing'
              ? 'no file backs this include — promote to create a local override.'
              : 'this resolves to a starter template — promote to make a local copy you can edit.'}
          </span>
          <button onClick={promote} style={primaryButton(theme)}>
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
        aria-label={`${data.filename}.md`}
        style={{
          ...fieldStyle(theme, dirty && !isExampleOrMissing),
          color: isExampleOrMissing ? theme.textDisabled : theme.textPrimary,
        }}
      />
      <div style={{ ...noteStyle(theme.textDisabled), fontSize: 12, marginTop: 8 }}>
        changes take effect on the next session · {content.length.toLocaleString()} chars
      </div>

      {/* Snapshots */}
      <div style={{ marginTop: 22 }}>
        <div style={{ ...noteStyle(theme.textSecondary), marginBottom: 6 }}>
          recent snapshots
          {isShared && data.affects_agents.length > 0 && (
            <span style={{ color: theme.textDisabled }}>
              {' '}· edits made through this agent · other agents may have edited this shared file independently
            </span>
          )}
        </div>
        {last5.length === 0 ? (
          <div style={noteStyle(theme.textDisabled)}>
            no snapshots yet · save an edit to start a history
          </div>
        ) : (
          <div>
            {last5.map((s) => (
              <div
                key={s.id}
                style={{
                  ...noteStyle(theme.textSecondary),
                  padding: '4px 0',
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '4px 10px',
                  alignItems: 'center',
                }}
              >
                <span style={{ color: theme.textPrimary }}>{formatTs(s.timestamp)}</span>
                <span>[{s.kind}]</span>
                <span style={{ color: theme.textDisabled }}>{s.bytes}b</span>
                <span style={{ flex: 1 }} />
                <button onClick={() => restore(s.id)} style={secondaryButton(theme, true)}>
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
  affects,
  filename,
  onCancel,
  onConfirm,
}: {
  theme: Theme
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
        padding: 16,
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        data-testid="shared-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shared-confirm-title"
        style={{
          background: theme.surface1,
          border: `1px solid ${theme.borderStrong}`,
          borderRadius: 6,
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.18)',
          padding: '22px 24px',
          maxWidth: 480,
        }}
      >
        <h2
          id="shared-confirm-title"
          style={{
            margin: '0 0 8px',
            fontFamily: JARVIS_FONTS.serif,
            fontSize: 18,
            fontWeight: 600,
            lineHeight: 1.3,
            color: theme.textPrimary,
          }}
        >
          edit shared file?
        </h2>
        <p style={{ margin: '0 0 18px', ...readStyle(theme, 16), color: theme.textSecondary }}>
          <code style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 13, color: theme.textPrimary }}>
            {filename}
          </code>{' '}
          is shared. This save also affects:{' '}
          <strong style={{ color: theme.textPrimary }}>{affects.join(', ')}</strong>.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={secondaryButton(theme)}>
            cancel
          </button>
          <button onClick={onConfirm} style={primaryButton(theme)}>
            edit shared file
          </button>
        </div>
      </div>
    </div>
  )
}

function formatTs(ts: string): string {
  const m = ts.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/)
  return m ? `${m[1]} ${m[2]}` : ts
}
