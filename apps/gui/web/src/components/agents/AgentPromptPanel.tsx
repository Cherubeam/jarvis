// AgentPromptPanel — editable textarea for prompts/system.md with Save/Revert.
// JARVIS renders a read-only explanation; save-on-disk creates a snapshot.

import { useEffect, useState } from 'react'

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { PromptResponse, PromptSaveResult } from '../../lib/types'

export function AgentPromptPanel({
  theme,
  hue,
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
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.error,
          marginTop: 28,
        }}
      >
        failed to load prompt: {error}
      </div>
    )
  }
  if (!data) {
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

  if (readOnly) {
    return (
      <div style={{ marginTop: 28 }}>
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textSecondary,
            background: theme.surface1,
            border: `1px solid ${theme.border}`,
            borderRadius: 6,
            padding: 14,
            marginBottom: 16,
            lineHeight: 1.6,
          }}
        >
          {data.explanation}
        </div>
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
            maxHeight: 480,
            overflow: 'auto',
          }}
        >
          {data.content}
        </pre>
      </div>
    )
  }

  return (
    <div style={{ marginTop: 24 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 10,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color: theme.textSecondary,
        }}
      >
        <span data-testid="prompt-path" style={{ color: theme.textDisabled }}>
          {data.path}
        </span>
        <span style={{ flex: 1 }} />
        {status === 'saved' && <span style={{ color: hue }}>saved ✓</span>}
        {status === 'error' && <span style={{ color: theme.error }}>error: {error}</span>}
        {dirty && (
          <button
            onClick={revert}
            style={{
              all: 'unset',
              cursor: 'pointer',
              padding: '6px 12px',
              borderRadius: 4,
              border: `1px solid ${theme.border}`,
              color: theme.textSecondary,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
            }}
          >
            revert
          </button>
        )}
        <button
          onClick={save}
          disabled={!dirty || status === 'saving'}
          style={{
            all: 'unset',
            cursor: dirty && status !== 'saving' ? 'pointer' : 'not-allowed',
            padding: '6px 14px',
            borderRadius: 4,
            background: dirty ? hue : theme.surface2,
            color: dirty ? theme.surface0 : theme.textDisabled,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: 0.3,
          }}
        >
          {status === 'saving' ? 'saving…' : 'save'}
        </button>
      </div>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        spellCheck={false}
        rows={28}
        style={{
          width: '100%',
          boxSizing: 'border-box',
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
          lineHeight: 1.55,
          padding: 14,
          color: theme.textPrimary,
          background: theme.surface1,
          border: `1px solid ${dirty ? hue : theme.border}`,
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
          marginTop: 8,
        }}
      >
        changes take effect on the next session · {content.length.toLocaleString()} chars
      </div>
    </div>
  )
}
