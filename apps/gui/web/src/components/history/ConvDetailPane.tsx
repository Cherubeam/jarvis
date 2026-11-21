// ConvDetailPane — right pane, laid out as a journal page: title and actions
// in the reading column, the five counts (incl. Handoffs) as a margin note,
// then Session metadata, Tools used and the Preview. Export is stubbed.

import { Fragment, useEffect, useState } from 'react'

import { speakerLabel } from '../../lib/speakerLabel'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { ConversationDetail, ConversationSummary } from '../../lib/types'

function formatDuration(ms: number): string {
  if (ms <= 0) return '—'
  const total = Math.floor(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`
  if (m > 0) return `${m}m ${String(s).padStart(2, '0')}s`
  return `${s}s`
}

export function ConvDetailPane({
  theme,
  accent,
  conversation,
  onResume,
  onDeleted,
}: {
  theme: Theme
  accent: string
  conversation: ConversationSummary | null
  onResume: (fileId: string) => void
  onDeleted?: (id: string) => void
}) {
  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  async function handleDelete(id: string) {
    if (deleting) return
    const ok = window.confirm(
      'Delete this conversation? This permanently removes the JSON file and any recall index entries.',
    )
    if (!ok) return
    setDeleting(true)
    setDeleteError(null)
    try {
      const r = await fetch(`/api/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' })
      if (!r.ok) {
        const body = await r.text()
        throw new Error(body || `HTTP ${r.status}`)
      }
      onDeleted?.(id)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setDeleteError(msg)
    } finally {
      setDeleting(false)
    }
  }

  useEffect(() => {
    if (!conversation) {
      setDetail(null)
      return
    }
    setLoading(true)
    setError(null)
    const ac = new AbortController()
    fetch(`/api/conversations/${encodeURIComponent(conversation.id)}`, { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<ConversationDetail>
      })
      .then((d) => {
        setDetail(d)
        setLoading(false)
      })
      .catch((e) => {
        if (e.name === 'AbortError') return
        setError(String(e.message || e))
        setLoading(false)
      })
    return () => ac.abort()
  }, [conversation?.id])

  if (!conversation) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.textDisabled,
        }}
      >
        select a conversation
      </div>
    )
  }

  const c = conversation
  const primaryAgent = c.agents[0] || 'JARVIS'
  const serif = theme.read === JARVIS_FONTS.serif

  const note = { fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.textDisabled }

  // A section starts with a serif heading over a rule, in the reading column.
  const sectionHeader = (label: string) => (
    <div className="jr-row" style={{ paddingTop: 22, paddingBottom: 4 }}>
      <div className="jr-gutter" />
      <h3
        style={{
          margin: 0,
          paddingBottom: 6,
          borderBottom: `1px solid ${theme.border}`,
          fontFamily: JARVIS_FONTS.serif,
          fontSize: 18,
          fontWeight: 600,
          lineHeight: 1.3,
          color: theme.textPrimary,
        }}
      >
        {label}
      </h3>
    </div>
  )

  // One line of a section: nothing in the gutter, the content in the column.
  const line = (children: React.ReactNode) => (
    <div className="jr-row dense">
      <div className="jr-gutter" />
      <div style={{ minWidth: 0 }}>{children}</div>
    </div>
  )

  const stat = (label: string, value: React.ReactNode) => (
    <>
      <dt>{label}</dt>
      <dd style={{ margin: 0, color: theme.textSecondary }}>{value}</dd>
    </>
  )

  return (
    <div
      className="jr-pane"
      style={{
        flex: 1,
        minWidth: 0,
        overflowY: 'auto',
        paddingTop: 18,
        paddingBottom: 48,
        boxSizing: 'border-box',
      }}
    >
      <div className="jr-row">
        <div className="jr-gutter" />
        <div style={{ minWidth: 0 }}>
          <h2
            style={{
              margin: 0,
              fontFamily: JARVIS_FONTS.serif,
              fontSize: 22,
              fontWeight: 600,
              color: theme.textPrimary,
              lineHeight: 1.25,
              overflowWrap: 'anywhere',
            }}
          >
            {c.title}
          </h2>
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textSecondary,
              marginTop: 8,
              display: 'flex',
              gap: '0 8px',
              flexWrap: 'wrap',
              alignItems: 'baseline',
            }}
          >
            <span>{c.date}</span>
            <span>·</span>
            {c.agents.length > 0 ? (
              <>
                <span>{speakerLabel(primaryAgent)}</span>
                {c.agents.slice(1).map((a) => (
                  <Fragment key={a}>
                    <span style={{ color: theme.textDisabled }}>+</span>
                    <span>{speakerLabel(a)}</span>
                  </Fragment>
                ))}
              </>
            ) : (
              <span style={{ color: theme.textDisabled }}>no agent</span>
            )}
            <span>·</span>
            <span>{formatDuration(c.duration_ms)}</span>
          </div>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: 10,
              marginTop: 16,
            }}
          >
            <button
              onClick={() => onResume(c.id)}
              title="Open in chat and continue from this conversation"
              style={{
                all: 'unset',
                cursor: 'pointer',
                padding: '9px 18px',
                borderRadius: 4,
                background: theme.textPrimary,
                color: theme.surface0,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              resume →
            </button>
            <button
              disabled
              title="Export is deferred to a later phase"
              style={{
                all: 'unset',
                cursor: 'not-allowed',
                padding: '8px 18px',
                borderRadius: 4,
                border: `1px solid ${theme.border}`,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 13,
                color: theme.textDisabled,
              }}
            >
              export
            </button>
            <button
              onClick={() => handleDelete(c.id)}
              disabled={deleting}
              title="Permanently delete this conversation"
              style={{
                all: 'unset',
                cursor: deleting ? 'wait' : 'pointer',
                marginLeft: 'auto',
                padding: '8px 18px',
                borderRadius: 4,
                border: `1px solid ${theme.error}`,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 13,
                color: theme.error,
                opacity: deleting ? 0.5 : 1,
              }}
            >
              {deleting ? 'deleting…' : 'delete'}
            </button>
          </div>
          {deleteError && (
            <div
              role="alert"
              style={{
                marginTop: 10,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 12,
                color: theme.error,
                overflowWrap: 'anywhere',
              }}
            >
              delete failed: {deleteError}
            </div>
          )}
        </div>
        {/* The five counts, as a margin note instead of a strip of tiles. */}
        <div className="jr-margin" style={{ minWidth: 0 }}>
          <dl
            style={{
              margin: 0,
              display: 'grid',
              gridTemplateColumns: 'max-content minmax(0, 1fr)',
              columnGap: 12,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              lineHeight: 1.6,
              color: theme.stats,
            }}
          >
            {stat('Cost', `$${c.cost.toFixed(4)}`)}
            {stat('Tokens', c.tokens.toLocaleString())}
            {stat('Messages', c.messages)}
            {stat('Tools', c.tool_calls)}
            {stat('Handoffs', c.handoffs)}
          </dl>
        </div>
      </div>

      {sectionHeader('Session')}
      {line(
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 13,
            color: theme.textSecondary,
            lineHeight: 1.7,
            overflowWrap: 'anywhere',
          }}
        >
          <div>
            model ·{' '}
            <span style={{ color: theme.textPrimary }}>{c.model || '—'}</span>
            {c.provider && (
              <span style={{ color: theme.textDisabled }}> ({c.provider})</span>
            )}
          </div>
          <div>
            path ·{' '}
            <span style={{ color: theme.textPrimary }}>
              ~/jarvis/data/conversations/{c.date.slice(0, 4)}/{c.id}.json
            </span>
          </div>
        </div>,
      )}

      {sectionHeader(`Tools used · ${c.tools.length}`)}
      {line(
        c.tools.length === 0 ? (
          <div style={note}>no tools · pure reasoning session</div>
        ) : (
          <ul
            style={{
              margin: 0,
              padding: 0,
              listStyle: 'none',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '2px 16px',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
              lineHeight: 1.7,
              color: theme.textSecondary,
            }}
          >
            {c.tools.map((t) => (
              <li key={t} style={{ overflowWrap: 'anywhere' }}>
                {t}
              </li>
            ))}
          </ul>
        ),
      )}

      {sectionHeader('Preview')}
      {loading && line(<div style={note}>loading…</div>)}
      {error &&
        line(
          <div style={{ ...note, color: theme.error }}>failed to load: {error}</div>,
        )}
      {!loading && !error && detail && (
        detail.preview.length === 0 ? (
          line(<div style={note}>no preview · hit resume to open the full session</div>)
        ) : (
          <>
            {detail.preview.map((m, i) => {
              const isUser = m.role === 'user'
              return (
                <div key={i} className="jr-row">
                  <div
                    className="jr-gutter"
                    style={{
                      fontFamily: JARVIS_FONTS.mono,
                      fontSize: 12,
                      color: isUser ? theme.textDisabled : theme.textSecondary,
                    }}
                  >
                    {isUser ? 'You' : speakerLabel(m.role)}
                  </div>
                  {/* What you typed stays in mono; the answer is set in the reading face. */}
                  <div
                    style={{
                      minWidth: 0,
                      fontFamily: isUser ? JARVIS_FONTS.mono : theme.read,
                      fontSize: isUser || !serif ? 14 : 17,
                      lineHeight: 1.6,
                      color: theme.textPrimary,
                      overflowWrap: 'anywhere',
                    }}
                  >
                    {m.text}
                  </div>
                </div>
              )
            })}
            {line(
              <button
                onClick={() => onResume(c.id)}
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  padding: '4px 0',
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 13,
                  color: accent,
                }}
              >
                open full transcript →
              </button>,
            )}
          </>
        )
      )}
    </div>
  )
}
