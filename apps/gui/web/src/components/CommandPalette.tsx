import { useEffect, useMemo, useRef, useState } from 'react'

import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { Agent } from '../lib/types'

/** The list of agents and their commands, opened with / or ⌘K. A plain panel in
 *  the typed face: a line to filter, then one row per command. */
export function CommandPalette({
  theme,
  open,
  onClose,
  onPick,
  agents,
}: {
  theme: Theme
  open: boolean
  onClose: () => void
  onPick: (a: Agent) => void
  agents: Agent[]
}) {
  const [q, setQ] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50)
    if (!open) setQ('')
  }, [open])

  const items = useMemo(() => {
    const ql = q.toLowerCase()
    return agents
      .filter((a) => a.command || a.name === 'JARVIS')
      .filter(
        (a) =>
          !ql ||
          a.name.toLowerCase().includes(ql) ||
          a.command.toLowerCase().includes(ql) ||
          a.description.toLowerCase().includes(ql),
      )
  }, [agents, q])

  if (!open) return null

  return (
    <div
      onClick={onClose}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 30,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'flex-start',
        padding: '12vh 16px 0',
      }}
    >
      <div
        role="dialog"
        aria-label="Commands"
        onClick={(ev) => ev.stopPropagation()}
        style={{
          width: 560,
          maxWidth: '100%',
          maxHeight: '60vh',
          background: theme.surface1,
          border: `1px solid ${theme.borderStrong}`,
          borderRadius: 6,
          boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          fontFamily: JARVIS_FONTS.mono,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '12px 16px',
            borderBottom: `1px solid ${theme.border}`,
          }}
        >
          <input
            ref={inputRef}
            value={q}
            onChange={(ev) => setQ(ev.target.value)}
            placeholder="type a command or agent name…"
            aria-label="type a command or agent name"
            style={{
              all: 'unset',
              flex: 1,
              minWidth: 0,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 14,
              lineHeight: 1.6,
              color: theme.textPrimary,
            }}
          />
          <span
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textDisabled,
            }}
          >
            esc
          </span>
        </div>
        <div style={{ overflowY: 'auto', padding: '6px 0' }}>
          {items.length === 0 && (
            <div
              style={{
                padding: '24px 16px',
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 13,
                color: theme.textDisabled,
              }}
            >
              no matches.{' '}
              <span style={{ color: theme.textSecondary }}>packages/agents/</span>
            </div>
          )}
          {items.map((a, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onPick(a)}
              onMouseEnter={(ev) => (ev.currentTarget.style.background = theme.surface3)}
              onMouseLeave={(ev) => (ev.currentTarget.style.background = 'transparent')}
              onFocus={(ev) => (ev.currentTarget.style.background = theme.surface3)}
              onBlur={(ev) => (ev.currentTarget.style.background = 'transparent')}
              style={{
                appearance: 'none',
                margin: 0,
                border: 0,
                background: 'transparent',
                font: 'inherit',
                textAlign: 'left',
                cursor: 'pointer',
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 180px) minmax(0, 1fr) auto',
                gap: 16,
                alignItems: 'baseline',
                padding: '9px 16px',
                width: '100%',
                boxSizing: 'border-box',
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 13,
                lineHeight: 1.5,
              }}
            >
              <span
                style={{
                  color: theme.textPrimary,
                  fontWeight: 600,
                  overflowWrap: 'anywhere',
                }}
              >
                {a.command || a.name}
              </span>
              <span style={{ color: theme.textSecondary }}>{a.description}</span>
              <span style={{ fontSize: 12, color: theme.textDisabled }}>
                {a.tools.length ? `${a.tools.length} tools` : ''}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
