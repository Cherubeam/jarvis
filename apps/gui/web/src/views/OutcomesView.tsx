// OutcomesView — list pending outcome recommendations and score them.
// Backed by /api/outcomes/pending + POST /api/outcomes/{file_id}/review.
//
// Laid out like the chat stream (`.jr-row` in index.html): short labels in the
// gutter, the recommendation and its review form in the reading column, the
// dates as a margin note. Items are separated by a rule, not boxed.

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

/** Reset for a real <button> that keeps the global focus ring (`all: unset`
 *  as an inline style would switch it off). */
const buttonReset: React.CSSProperties = {
  appearance: 'none',
  margin: 0,
  padding: 0,
  border: 0,
  background: 'transparent',
  font: 'inherit',
  color: 'inherit',
  cursor: 'pointer',
}

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
    <div
      className="jr-pane"
      style={{ flex: 1, overflow: 'auto', minWidth: 0, background: theme.surface0, paddingBottom: 64 }}
    >
      <div className="jr-row" style={{ paddingTop: 36, paddingBottom: 18 }}>
        <div className="jr-gutter" />
        <div style={{ minWidth: 0 }}>
          <h1
            style={{
              margin: 0,
              fontFamily: JARVIS_FONTS.serif,
              fontSize: 30,
              fontWeight: 600,
              lineHeight: 1.2,
              color: theme.textPrimary,
            }}
          >
            Outcomes
          </h1>
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
              color: theme.textSecondary,
              marginTop: 8,
            }}
          >
            {items === null
              ? 'loading…'
              : `${items.length} item(s) due for review · data/outcomes/`}
          </div>
        </div>
      </div>

      {loadError && (
        <div className="jr-row">
          <div className="jr-gutter" />
          <div
            style={{
              minWidth: 0,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
              color: theme.error,
            }}
          >
            failed to load: {loadError}
          </div>
        </div>
      )}

      {items !== null && items.length === 0 && !loadError && (
        <div className="jr-row">
          <div className="jr-gutter" />
          <div
            style={{
              minWidth: 0,
              borderTop: `1px solid ${theme.border}`,
              paddingTop: 18,
              fontFamily: theme.read,
              fontSize: 16,
              lineHeight: 1.5,
              color: theme.textSecondary,
            }}
          >
            No items due for review.
          </div>
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

  const gutterLabel: React.CSSProperties = {
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 12,
    color: theme.textDisabled,
  }

  return (
    <article style={{ marginBottom: 22 }}>
      <div className="jr-row">
        <div className="jr-gutter" />
        <div style={{ minWidth: 0, borderTop: `1px solid ${theme.border}`, paddingTop: 18 }}>
          <h2
            style={{
              margin: 0,
              fontFamily: JARVIS_FONTS.serif,
              fontSize: 20,
              fontWeight: 600,
              lineHeight: 1.3,
              color: theme.textPrimary,
            }}
          >
            {item.what || '(no title)'}
          </h2>
          {item.why && (
            <div
              style={{
                fontFamily: theme.read,
                fontSize: 16,
                color: theme.textSecondary,
                marginTop: 6,
                lineHeight: 1.5,
              }}
            >
              {item.why}
            </div>
          )}
        </div>
        <div
          className="jr-margin"
          style={{
            minWidth: 0,
            paddingTop: 18,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            lineHeight: 1.6,
            color: theme.stats,
          }}
        >
          {item.created_at && <div>created {item.created_at.slice(0, 10)}</div>}
          <div>revisit {item.revisit_at}</div>
        </div>
      </div>

      {item.success_looks_like && (
        <div className="jr-row dense">
          <div className="jr-gutter" style={gutterLabel}>
            success:
          </div>
          <div
            style={{
              minWidth: 0,
              fontFamily: theme.read,
              fontSize: 15,
              lineHeight: 1.5,
              color: theme.textSecondary,
            }}
          >
            {item.success_looks_like}
          </div>
        </div>
      )}

      <div className="jr-row dense">
        <div className="jr-gutter" />
        <div style={{ minWidth: 0, display: 'flex', flexWrap: 'wrap', gap: '4px 20px' }}>
          {VERDICTS.map((v) => {
            const active = verdict === v
            return (
              <button
                key={v}
                type="button"
                onClick={() => setVerdict(v)}
                aria-pressed={active}
                style={{
                  ...buttonReset,
                  padding: '6px 0',
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 13,
                  color: active ? theme.textPrimary : theme.textSecondary,
                  textDecoration: active ? 'underline' : 'none',
                  textUnderlineOffset: 4,
                }}
              >
                {VERDICT_LABELS[v]}
              </button>
            )
          })}
        </div>
      </div>

      <div className="jr-row dense">
        <div className="jr-gutter" style={gutterLabel}>
          quality:
        </div>
        <div style={{ minWidth: 0, display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 4 }}>
          {[1, 2, 3, 4, 5].map((n) => {
            const active = n <= quality
            return (
              <button
                key={n}
                type="button"
                onClick={() => setQuality(n)}
                title={`${n} star${n > 1 ? 's' : ''}`}
                aria-pressed={n === quality}
                style={{
                  ...buttonReset,
                  padding: '5px 12px',
                  borderRadius: 4,
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 13,
                  color: active ? theme.textPrimary : theme.textSecondary,
                  background: active ? theme.surface3 : 'transparent',
                  textAlign: 'center',
                }}
              >
                {n}
              </button>
            )
          })}
        </div>
      </div>

      <div className="jr-row dense">
        <div className="jr-gutter" />
        <div style={{ minWidth: 0 }}>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Retrospective note — what actually happened, why…"
            aria-label="Retrospective note"
            style={{
              display: 'block',
              width: '100%',
              boxSizing: 'border-box',
              minHeight: 76,
              padding: '8px 12px',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 14,
              lineHeight: 1.5,
              color: theme.textPrimary,
              background: theme.surface2,
              border: `1px solid ${theme.border}`,
              borderRadius: 4,
              resize: 'vertical',
            }}
          />
        </div>
      </div>

      <div className="jr-row dense">
        <div className="jr-gutter" />
        <div style={{ minWidth: 0, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
          <button
            type="button"
            disabled={!canSave}
            onClick={save}
            style={{
              ...buttonReset,
              cursor: canSave ? 'pointer' : 'not-allowed',
              padding: '9px 18px',
              borderRadius: 4,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
              fontWeight: 600,
              color: canSave ? theme.surface0 : theme.textDisabled,
              background: canSave ? theme.textPrimary : theme.surface3,
            }}
          >
            {status.kind === 'saving' ? 'saving…' : 'save review'}
          </button>
          {status.kind === 'error' && (
            <span
              style={{
                minWidth: 0,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 12,
                color: theme.error,
                overflowWrap: 'anywhere',
              }}
            >
              {status.message}
            </span>
          )}
        </div>
      </div>
    </article>
  )
}
