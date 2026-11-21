// AgentContextPanel — resolved prompt text (with {placeholder} substitutions applied).
// Read-only preview of what the LLM actually sees.

import { useEffect, useState } from 'react'

import type { Theme } from '../../lib/tokens'
import type { PromptResolved } from '../../lib/types'
import { JournalRow, noteStyle, previewStyle, secondaryButton } from './journal'

export function AgentContextPanel({
  theme,
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
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.error)}>failed to load resolved prompt: {error}</div>
      </JournalRow>
    )
  }
  if (resolved == null) {
    return (
      <JournalRow theme={theme} style={{ paddingTop: 18 }}>
        <div style={noteStyle(theme.textDisabled)}>loading…</div>
      </JournalRow>
    )
  }

  return (
    <JournalRow theme={theme} wide style={{ paddingTop: 18 }}>
      <div
        style={{
          ...noteStyle(theme.textSecondary),
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 10,
          marginBottom: 12,
        }}
      >
        <span style={{ color: theme.textDisabled }}>
          placeholders expanded · {resolved.length.toLocaleString()} chars
        </span>
        <span style={{ flex: 1 }} />
        {copied && <span>copied ✓</span>}
        <button onClick={copy} style={secondaryButton(theme)}>
          copy
        </button>
      </div>
      <pre style={previewStyle(theme, 600)}>{resolved}</pre>
    </JournalRow>
  )
}
