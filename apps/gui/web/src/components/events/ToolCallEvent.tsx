import { useState } from 'react'

import { Icon } from '../Icon'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import { Row } from './Row'

export type ToolCallShape = {
  id: string
  agent: string
  tool: string
  args: Record<string, unknown>
  result: { summary?: string; preview?: string; path?: string }
  elapsed_ms: number
}

export function ToolCallEvent({
  e,
  theme,
  dense,
  style = 'card',
}: {
  e: ToolCallShape
  theme: Theme
  dense?: boolean
  style?: 'card' | 'inline' | 'dim'
}) {
  const [open, setOpen] = useState(false)

  if (style === 'dim') {
    return (
      <Row theme={theme} label="tool" labelColor={theme.tool} mono dense={dense}>
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textSecondary,
            opacity: 0.75,
          }}
        >
          <span style={{ color: theme.tool }}>[Tool: {e.tool}]</span>{' '}
          <span>{e.result.summary}</span>
          <span style={{ marginLeft: 8, opacity: 0.6 }}>{e.elapsed_ms}ms</span>
        </div>
      </Row>
    )
  }

  if (style === 'inline') {
    return (
      <Row theme={theme} label="tool" labelColor={theme.tool} mono dense={dense}>
        <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 13 }}>
          <span style={{ color: theme.tool, fontWeight: 600 }}>[Tool: {e.tool}]</span>
          <span style={{ color: theme.textSecondary }}>
            {' '}
            · {e.result.summary} · {e.elapsed_ms}ms
          </span>
        </div>
      </Row>
    )
  }

  return (
    <Row theme={theme} label="tool" labelColor={theme.tool} mono dense={dense}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          all: 'unset',
          display: 'block',
          width: '100%',
          cursor: 'pointer',
          background: theme.surface2,
          border: `1px solid ${theme.border}`,
          borderRadius: 8,
          padding: '10px 12px',
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
          boxSizing: 'border-box',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              color: theme.tool,
              fontWeight: 600,
            }}
          >
            <Icon name="tool" size={13} />
            {e.tool}
          </div>
          <div style={{ flex: 1, color: theme.textSecondary }}>{e.result.summary}</div>
          <div style={{ color: theme.textSecondary, opacity: 0.7 }}>{e.elapsed_ms}ms</div>
          <div
            style={{
              color: theme.textSecondary,
              transform: open ? 'rotate(90deg)' : 'none',
              transition: 'transform 120ms',
            }}
          >
            <Icon name="right" size={12} />
          </div>
        </div>
        {open && (
          <div
            style={{
              marginTop: 10,
              paddingTop: 10,
              borderTop: `1px dashed ${theme.borderStrong}`,
              color: theme.textSecondary,
              fontSize: 12,
              lineHeight: 1.6,
            }}
          >
            <div style={{ marginBottom: 6 }}>
              <span style={{ color: theme.textDisabled }}>args </span>
              <span style={{ color: theme.textPrimary }}>{JSON.stringify(e.args)}</span>
            </div>
            {e.result.path && (
              <div style={{ marginBottom: 6 }}>
                <span style={{ color: theme.textDisabled }}>path </span>
                <span style={{ color: theme.assistant }}>{e.result.path}</span>
              </div>
            )}
            {e.result.preview && (
              <pre
                style={{
                  margin: '6px 0 0',
                  padding: '8px 10px',
                  background: theme.surface1,
                  borderRadius: 6,
                  color: theme.textSecondary,
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                  overflow: 'auto',
                }}
              >
                {e.result.preview}
              </pre>
            )}
          </div>
        )}
      </button>
    </Row>
  )
}
