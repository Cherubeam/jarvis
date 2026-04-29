// ConvDetailPane — right pane with 5-stat strip (incl. Handoffs), Session
// metadata, Tools chips, Preview. Resume/Export stubbed. Ported from
// JARVIS GUI.html 3288-3479.

import { Fragment, useEffect, useState } from 'react'

import { hueFor } from '../../lib/agentHues'
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
  onResume: () => void
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
  const hue = hueFor(primaryAgent, accent)

  const sectionHeader = (label: string) => (
    <div
      style={{
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 10,
        letterSpacing: 1.4,
        color: theme.textDisabled,
        textTransform: 'uppercase',
        marginTop: 22,
        marginBottom: 10,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span>{label}</span>
      <span style={{ flex: 1, height: 1, background: theme.border }} />
    </div>
  )

  const stat = (label: string, value: React.ReactNode, color?: string, isLast = false) => (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        padding: '10px 12px',
        borderRight: isLast ? 'none' : `1px solid ${theme.border}`,
      }}
    >
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 9.5,
          letterSpacing: 1.3,
          color: theme.textDisabled,
          textTransform: 'uppercase',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 15,
          fontWeight: 600,
          color: color || theme.textPrimary,
        }}
      >
        {value}
      </div>
    </div>
  )

  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        overflow: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          maxWidth: 720,
          margin: '0 auto',
          padding: '28px 36px 48px',
          width: '100%',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 10 }}>
          <div
            style={{
              width: 4,
              height: 40,
              background: hue,
              borderRadius: 2,
              flexShrink: 0,
            }}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontFamily: JARVIS_FONTS.sans,
                fontSize: 20,
                fontWeight: 600,
                color: theme.textPrimary,
                letterSpacing: -0.2,
                lineHeight: 1.25,
              }}
            >
              {c.title}
            </div>
            <div
              style={{
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 11,
                color: theme.textSecondary,
                marginTop: 6,
                display: 'flex',
                gap: 8,
                flexWrap: 'wrap',
                alignItems: 'center',
              }}
            >
              <span>{c.date}</span>
              <span>·</span>
              {c.agents.length > 0 ? (
                <>
                  <span style={{ color: hue }}>{speakerLabel(primaryAgent)}</span>
                  {c.agents.slice(1).map((a) => (
                    <Fragment key={a}>
                      <span style={{ color: theme.textDisabled }}>+</span>
                      <span style={{ color: hueFor(a, accent) }}>{speakerLabel(a)}</span>
                    </Fragment>
                  ))}
                </>
              ) : (
                <span style={{ color: theme.textDisabled }}>no agent</span>
              )}
              <span>·</span>
              <span>{formatDuration(c.duration_ms)}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            <button
              onClick={onResume}
              title="Resume is deferred — currently returns to chat"
              style={{
                all: 'unset',
                cursor: 'pointer',
                padding: '7px 14px',
                borderRadius: 5,
                background: accent,
                color: theme.surface0,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: 0.3,
                opacity: 0.7,
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
                padding: '7px 12px',
                borderRadius: 5,
                border: `1px solid ${theme.border}`,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 11,
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
                padding: '7px 12px',
                borderRadius: 5,
                border: `1px solid ${theme.error}`,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 11,
                color: theme.error,
                opacity: deleting ? 0.5 : 1,
              }}
            >
              {deleting ? 'deleting…' : 'delete'}
            </button>
          </div>
        </div>
        {deleteError && (
          <div
            style={{
              marginTop: 10,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              color: theme.error,
            }}
          >
            delete failed: {deleteError}
          </div>
        )}

        {/* 5-stat strip */}
        <div
          style={{
            display: 'flex',
            border: `1px solid ${theme.border}`,
            borderRadius: 6,
            background: theme.surface1,
            marginTop: 16,
            overflow: 'hidden',
          }}
        >
          {stat('Cost', `$${c.cost.toFixed(4)}`, theme.cost)}
          {stat('Tokens', c.tokens.toLocaleString())}
          {stat('Messages', c.messages)}
          {stat('Tools', c.tool_calls)}
          {stat('Handoffs', c.handoffs, undefined, true)}
        </div>

        {sectionHeader('Session')}
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textSecondary,
            lineHeight: 1.8,
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
            <span style={{ color: theme.assistant }}>
              ~/jarvis/data/conversations/{c.date.slice(0, 4)}/{c.id}.json
            </span>
          </div>
        </div>

        {sectionHeader(`Tools used · ${c.tools.length}`)}
        {c.tools.length === 0 ? (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textDisabled,
            }}
          >
            no tools · pure reasoning session
          </div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {c.tools.map((t) => (
              <span
                key={t}
                style={{
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                  padding: '4px 9px',
                  borderRadius: 4,
                  background: theme.surface2,
                  color: theme.tool,
                  border: `1px solid ${theme.border}`,
                }}
              >
                {t}
              </span>
            ))}
          </div>
        )}

        {sectionHeader('Preview')}
        {loading && (
          <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.textDisabled }}>
            loading…
          </div>
        )}
        {error && (
          <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.error }}>
            failed to load: {error}
          </div>
        )}
        {!loading && !error && detail && (
          detail.preview.length === 0 ? (
            <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.textDisabled }}>
              no preview · hit resume to open the full session
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {detail.preview.map((m, i) => {
                const isUser = m.role === 'user'
                const agentHue = isUser ? theme.user : hueFor(m.role, accent)
                return (
                  <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                    <div
                      style={{
                        width: 64,
                        flexShrink: 0,
                        paddingTop: 2,
                        fontFamily: JARVIS_FONTS.mono,
                        fontSize: 11,
                        fontWeight: 700,
                        color: agentHue,
                        textAlign: 'right',
                        letterSpacing: 0.2,
                      }}
                    >
                      {isUser ? 'You' : speakerLabel(m.role)}
                    </div>
                    <div
                      style={{
                        flex: 1,
                        fontSize: 14,
                        lineHeight: 1.55,
                        color: theme.textPrimary,
                      }}
                    >
                      {m.text}
                    </div>
                  </div>
                )
              })}
              <button
                onClick={onResume}
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  alignSelf: 'flex-start',
                  marginTop: 4,
                  padding: '6px 10px',
                  borderRadius: 4,
                  border: `1px dashed ${theme.border}`,
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                  color: theme.textSecondary,
                }}
              >
                open full transcript →
              </button>
            </div>
          )
        )}
      </div>
    </div>
  )
}
