import { useState } from 'react'

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

/** A tool call is a footnote to the answer, not a card: one muted line that
 *  names the tool and what came back. The default style ('card' in Tweaks, kept
 *  for stored settings) unfolds to show arguments, path and a preview. */
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

  // A tool's summary can be a screenful of JSON. Folded, it stays on one line;
  // unfolded, the whole summary is shown below.
  const line = (
    <span style={{ display: 'flex', gap: 8, minWidth: 0 }}>
      <span style={{ color: theme.textPrimary, flexShrink: 0 }}>{e.tool}</span>
      <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {e.result.summary}
      </span>
      <span style={{ flexShrink: 0, marginLeft: 'auto' }}>{e.elapsed_ms}ms</span>
    </span>
  )

  if (style === 'dim' || style === 'inline') {
    return (
      <Row theme={theme} label="" dense={dense}>
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: style === 'dim' ? 12 : 13,
            color: style === 'dim' ? theme.textDisabled : theme.textSecondary,
          }}
        >
          {line}
        </div>
      </Row>
    )
  }

  return (
    <Row theme={theme} label="" dense={dense}>
      <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 13, color: theme.textSecondary }}>
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          style={{ all: 'unset', cursor: 'pointer', display: 'flex', width: '100%', boxSizing: 'border-box' }}
        >
          <span
            aria-hidden="true"
            style={{
              flexShrink: 0,
              width: 16,
              textAlign: 'center',
              marginRight: 4,
              color: theme.textDisabled,
              transform: open ? 'rotate(90deg)' : 'none',
              transition: 'transform 120ms',
            }}
          >
            ›
          </span>
          <span style={{ flex: 1, minWidth: 0 }}>{line}</span>
        </button>
        {open && (
          <div
            style={{
              margin: '6px 0 2px 5px',
              padding: '2px 0 2px 14px',
              borderLeft: `1px solid ${theme.borderStrong}`,
              fontSize: 12,
              lineHeight: 1.6,
            }}
          >
            {e.result.summary && (
              <div style={{ wordBreak: 'break-word' }}>
                <span style={{ color: theme.textDisabled }}>result </span>
                <span style={{ color: theme.textPrimary }}>{e.result.summary}</span>
              </div>
            )}
            <div>
              <span style={{ color: theme.textDisabled }}>args </span>
              <span style={{ color: theme.textPrimary, wordBreak: 'break-word' }}>
                {JSON.stringify(e.args)}
              </span>
            </div>
            {e.result.path && (
              <div>
                <span style={{ color: theme.textDisabled }}>path </span>
                <span style={{ color: theme.textPrimary }}>{e.result.path}</span>
              </div>
            )}
            {e.result.preview && (
              <pre
                style={{
                  margin: '6px 0 0',
                  color: theme.textSecondary,
                  fontFamily: JARVIS_FONTS.mono,
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
      </div>
    </Row>
  )
}
