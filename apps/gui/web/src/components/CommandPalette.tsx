import { useEffect, useMemo, useRef, useState } from 'react'

import { Icon } from './Icon'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { Agent } from '../lib/types'

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
        paddingTop: '12vh',
      }}
    >
      <div
        onClick={(ev) => ev.stopPropagation()}
        style={{
          width: 560,
          maxHeight: '60vh',
          background: theme.surface1,
          border: `1px solid ${theme.borderStrong}`,
          borderRadius: 12,
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '14px 18px',
            borderBottom: `1px solid ${theme.border}`,
          }}
        >
          <Icon name="slash" size={14} color={theme.assistant} />
          <input
            ref={inputRef}
            value={q}
            onChange={(ev) => setQ(ev.target.value)}
            placeholder="type a command or agent name…"
            style={{
              all: 'unset',
              flex: 1,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 15,
              color: theme.textPrimary,
            }}
          />
          <span
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 10,
              color: theme.textDisabled,
              padding: '2px 6px',
              border: `1px solid ${theme.border}`,
              borderRadius: 3,
            }}
          >
            esc
          </span>
        </div>
        <div style={{ overflowY: 'auto', padding: '6px 0' }}>
          {items.length === 0 && (
            <div
              style={{
                padding: '28px 20px',
                textAlign: 'center',
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 12,
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
              onClick={() => onPick(a)}
              onMouseEnter={(ev) => (ev.currentTarget.style.background = theme.surface2)}
              onMouseLeave={(ev) => (ev.currentTarget.style.background = 'transparent')}
              style={{
                all: 'unset',
                cursor: 'pointer',
                display: 'grid',
                gridTemplateColumns: '180px 1fr auto',
                gap: 16,
                alignItems: 'center',
                padding: '10px 18px',
                width: '100%',
                boxSizing: 'border-box',
              }}
            >
              <span
                style={{
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 13,
                  color: a.command ? theme.assistant : theme.tool,
                  fontWeight: 600,
                }}
              >
                {a.command || a.name}
              </span>
              <span style={{ fontSize: 13, color: theme.textPrimary }}>{a.description}</span>
              <span
                style={{
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 10.5,
                  color: theme.textDisabled,
                }}
              >
                {a.tools.length ? `${a.tools.length} tools` : ''}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
