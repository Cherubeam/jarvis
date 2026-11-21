// AgentPromptPanel — editable textarea for prompts/system.md with Save/Revert.
// JARVIS renders a read-only explanation; save-on-disk creates a snapshot.

import { useEffect, useState } from 'react'

import type { Theme } from '../../lib/tokens'
import type { PromptResponse, PromptSaveResult } from '../../lib/types'
import {
  JournalRow,
  fieldStyle,
  noteStyle,
  previewStyle,
  primaryButton,
  readStyle,
  secondaryButton,
} from './journal'

export function AgentPromptPanel({
  theme,
  agentId,
  onSaved,
}: {
  theme: Theme
  hue: string
  agentId: string
  onSaved: () => void
}) {
  const [data, setData] = useState<PromptResponse | null>(null)
  const [original, setOriginal] = useState('')
  const [content, setContent] = useState('')
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const ac = new AbortController()
    setStatus('idle')
    setError(null)
    fetch(`/api/agents/${encodeURIComponent(agentId)}/prompt`, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body: PromptResponse) => {
        setData(body)
        setOriginal(body.content)
        setContent(body.content)
      })
      .catch((e) => {
        if (e?.name !== 'AbortError') setError(e?.message || String(e))
      })
    return () => ac.abort()
  }, [agentId])

  const dirty = content !== original
  const readOnly = data?.editable === false

  const save = async () => {
    if (!dirty || readOnly) return
    setStatus('saving')
    setError(null)
    try {
      const r = await fetch(`/api/agents/${encodeURIComponent(agentId)}/prompt`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const body = (await r.json()) as PromptSaveResult
      setOriginal(content)
      setData((prev) =>
        prev
          ? { ...prev, bytes: body.bytes, last_modified_iso: body.last_modified_iso }
          : prev,
      )
      setStatus('saved')
      onSaved()
      window.setTimeout(() => setStatus('idle'), 1500)
    } catch (e) {
      setError((e as Error).message || String(e))
      setStatus('error')
    }
  }

  const revert = () => setContent(original)

  if (error && !data) {
    return (
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.error)}>failed to load prompt: {error}</div>
      </JournalRow>
    )
  }
  if (!data) {
    return (
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.textDisabled)}>loading…</div>
      </JournalRow>
    )
  }

  if (readOnly) {
    return (
      <>
        <JournalRow theme={theme} style={{ paddingTop: 18 }}>
          <p style={{ margin: 0, ...readStyle(theme, 16), color: theme.textSecondary }}>
            {data.explanation}
          </p>
        </JournalRow>
        <JournalRow theme={theme} wide>
          <pre style={previewStyle(theme, 480)}>{data.content}</pre>
        </JournalRow>
      </>
    )
  }

  const canSave = dirty && status !== 'saving'

  return (
    <JournalRow theme={theme} wide style={{ paddingTop: 18 }}>
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
          data-testid="prompt-path"
          style={{ color: theme.textDisabled, overflowWrap: 'anywhere' }}
        >
          {data.path}
        </span>
        <span style={{ flex: 1 }} />
        {status === 'saved' && <span>saved ✓</span>}
        {status === 'error' && <span style={{ color: theme.error }}>error: {error}</span>}
        {dirty && (
          <button onClick={revert} style={secondaryButton(theme)}>
            revert
          </button>
        )}
        <button onClick={save} disabled={!canSave} style={primaryButton(theme, canSave)}>
          {status === 'saving' ? 'saving…' : 'save'}
        </button>
      </div>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        spellCheck={false}
        rows={28}
        aria-label="System prompt"
        style={fieldStyle(theme, dirty)}
      />
      <div style={{ ...noteStyle(theme.textDisabled), fontSize: 12, marginTop: 8 }}>
        changes take effect on the next session · {content.length.toLocaleString()} chars
      </div>
    </JournalRow>
  )
}
