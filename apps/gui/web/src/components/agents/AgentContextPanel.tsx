// AgentContextPanel — resolved prompt text (with {placeholder} substitutions applied).
// Read-only preview of what the LLM actually sees.

import { useEffect, useState } from 'react'

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { PromptResolved } from '../../lib/types'

export function AgentContextPanel({
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
  const [resolved, setResolved] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const ac = new AbortController()
    setError(null)
    fetch(`/api/agents/${encodeURIComponent(agentId)}/prompt/resolved`, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body: PromptResolved) => setResolved(body.resolved_content))
      .catch((e) => {
        if (e?.name !== 'AbortError') setError(e?.message || String(e))
      })
    return () => ac.abort()
  }, [agentId, refreshToken])

  const copy = async () => {
    if (resolved == null) return
    try {
      await navigator.clipboard.writeText(resolved)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard blocked — silently no-op.
    }
  }

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
        failed to load resolved prompt: {error}
      </div>
    )
  }
  if (resolved == null) {
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
        <span style={{ color: theme.textDisabled }}>
          placeholders expanded · {resolved.length.toLocaleString()} chars
        </span>
        <span style={{ flex: 1 }} />
        {copied && <span style={{ color: hue }}>copied ✓</span>}
        <button
          onClick={copy}
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
          copy
        </button>
      </div>
      <pre
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          lineHeight: 1.55,
          color: theme.textPrimary,
          background: theme.surface2,
          border: `1px solid ${theme.border}`,
          borderRadius: 6,
          padding: 14,
          margin: 0,
          whiteSpace: 'pre-wrap',
          maxHeight: 600,
          overflow: 'auto',
        }}
      >
        {resolved}
      </pre>
    </div>
  )
}
