// OutcomesView — list pending outcome recommendations and score them.
// Backed by /api/outcomes/pending + POST /api/outcomes/{file_id}/review.

import { useEffect, useState } from 'react'

import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { OutcomeVerdict, PendingOutcome, ReviewOutcomeResult } from '../lib/types'

type CardStatus =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'error'; message: string }

const VERDICT_LABELS: Record<OutcomeVerdict, string> = {
  happened: 'Happened',
  didnt: "Didn't",
  partial: 'Partial',
}

const VERDICTS: OutcomeVerdict[] = ['happened', 'didnt', 'partial']

export function OutcomesView({
  theme,
  accent,
  refreshToken,
}: {
  theme: Theme
  accent: string
  refreshToken: number
}) {
  const [items, setItems] = useState<PendingOutcome[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    const ac = new AbortController()
    setLoadError(null)
    fetch('/api/outcomes/pending', { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: PendingOutcome[]) => setItems(data))
      .catch((e) => {
        if (e?.name !== 'AbortError') setLoadError((e as Error).message || String(e))
      })
    return () => ac.abort()
  }, [refreshToken])

  const onReviewed = (file_id: string) => {
    setItems((prev) => (prev ? prev.filter((i) => i.file_id !== file_id) : prev))
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', minWidth: 0, background: theme.surface0 }}>
      <div style={{ maxWidth: 880, margin: '0 auto', padding: '40px 48px 64px' }}>
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              fontFamily: JARVIS_FONTS.sans,
              fontSize: 24,
              fontWeight: 600,
              color: theme.textPrimary,
              letterSpacing: -0.3,
            }}
          >
            Outcomes
          </div>
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              color: theme.textSecondary,
              marginTop: 4,
            }}
          >
            {items === null
              ? 'loading…'
              : `${items.length} item(s) due for review · data/outcomes/`}
          </div>
        </div>

        {loadError && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.error,
              marginBottom: 12,
            }}
          >
            failed to load: {loadError}
          </div>
        )}

        {items !== null && items.length === 0 && !loadError && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textDisabled,
              padding: '40px 0',
              textAlign: 'center',
            }}
          >
            No items due for review.
          </div>
        )}

        {items?.map((item) => (
          <OutcomeCard
            key={item.file_id}
            theme={theme}
            accent={accent}
            item={item}
            onReviewed={onReviewed}
          />
        ))}
      </div>
    </div>
  )
}

function OutcomeCard({
  theme,
  accent,
  item,
  onReviewed,
}: {
  theme: Theme
  accent: string
  item: PendingOutcome
  onReviewed: (file_id: string) => void
}) {
  const [verdict, setVerdict] = useState<OutcomeVerdict | null>(null)
  const [quality, setQuality] = useState<number>(0)
  const [note, setNote] = useState('')
  const [status, setStatus] = useState<CardStatus>({ kind: 'idle' })

  const canSave = verdict !== null && quality >= 1 && quality <= 5 && status.kind !== 'saving'

  const save = async () => {
    if (!canSave || verdict === null) return
    setStatus({ kind: 'saving' })
    try {
      const r = await fetch(
        `/api/outcomes/${encodeURIComponent(item.file_id)}/review`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ outcome: verdict, quality, note }),
        },
      )
      if (!r.ok) {
        const body = await r.text()
        throw new Error(`HTTP ${r.status}: ${body}`)
      }
      const result = (await r.json()) as ReviewOutcomeResult
      onReviewed(result.file_id)
    } catch (e) {
      setStatus({ kind: 'error', message: (e as Error).message || String(e) })
    }
  }

  return (
    <div
      style={{
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        background: theme.surface1,
        padding: '18px 20px',
        marginBottom: 14,
      }}
    >
      <div
        style={{
          fontFamily: JARVIS_FONTS.sans,
          fontSize: 15,
          fontWeight: 600,
          color: theme.textPrimary,
          letterSpacing: -0.1,
          marginBottom: 4,
        }}
      >
        {item.what || '(no title)'}
      </div>
      {item.why && (
        <div
          style={{
            fontFamily: JARVIS_FONTS.sans,
            fontSize: 13,
            color: theme.textSecondary,
            marginBottom: 8,
            lineHeight: 1.4,
          }}
        >
          {item.why}
        </div>
      )}
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color: theme.textDisabled,
          marginBottom: 12,
        }}
      >
        {item.created_at && <span>created {item.created_at.slice(0, 10)}</span>}
        {item.created_at && <span style={{ margin: '0 6px' }}>·</span>}
        <span>revisit {item.revisit_at}</span>
      </div>
      {item.success_looks_like && (
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: theme.textSecondary,
            marginBottom: 14,
            paddingLeft: 8,
            borderLeft: `2px solid ${theme.border}`,
          }}
        >
          success: {item.success_looks_like}
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {VERDICTS.map((v) => {
          const active = verdict === v
          return (
            <button
              key={v}
              onClick={() => setVerdict(v)}
              style={{
                all: 'unset',
                cursor: 'pointer',
                padding: '6px 12px',
                borderRadius: 6,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 11,
                border: active ? `1px solid ${accent}` : `1px solid ${theme.border}`,
                background: active ? theme.surface2 : 'transparent',
                color: active ? accent : theme.textSecondary,
              }}
            >
              {VERDICT_LABELS[v]}
            </button>
          )
        })}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: theme.textDisabled,
            minWidth: 70,
          }}
        >
          quality:
        </div>
        {[1, 2, 3, 4, 5].map((n) => {
          const active = n <= quality
          return (
            <button
              key={n}
              onClick={() => setQuality(n)}
              title={`${n} star${n > 1 ? 's' : ''}`}
              style={{
                all: 'unset',
                cursor: 'pointer',
                padding: '4px 8px',
                borderRadius: 4,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 12,
                color: active ? accent : theme.textDisabled,
                border: `1px solid ${active ? accent : theme.border}`,
                minWidth: 14,
                textAlign: 'center',
              }}
            >
              {n}
            </button>
          )
        })}
      </div>

      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Retrospective note — what actually happened, why…"
        style={{
          width: '100%',
          boxSizing: 'border-box',
          minHeight: 72,
          padding: 10,
          fontFamily: JARVIS_FONTS.sans,
          fontSize: 13,
          color: theme.textPrimary,
          background: theme.surface0,
          border: `1px solid ${theme.border}`,
          borderRadius: 6,
          resize: 'vertical',
          marginBottom: 12,
        }}
      />

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button
          disabled={!canSave}
          onClick={save}
          style={{
            all: 'unset',
            cursor: canSave ? 'pointer' : 'not-allowed',
            padding: '7px 14px',
            borderRadius: 6,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: canSave ? theme.surface0 : theme.textDisabled,
            background: canSave ? accent : theme.surface2,
            border: `1px solid ${canSave ? accent : theme.border}`,
          }}
        >
          {status.kind === 'saving' ? 'saving…' : 'save review'}
        </button>
        {status.kind === 'error' && (
          <span
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              color: theme.error,
            }}
          >
            {status.message}
          </span>
        )}
      </div>
    </div>
  )
}
