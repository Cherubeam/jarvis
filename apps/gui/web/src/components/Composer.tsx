import { useRef, useState } from 'react'

import { JARVIS_FONTS, type Theme } from '../lib/tokens'

/** The next line of the page. No box: a rule above, the same gutter and column
 *  as the stream, and you write where the conversation left off. */
export function Composer({
  theme,
  accent,
  onSubmit,
  onOpenPalette,
  onValueChange,
  disabled,
}: {
  theme: Theme
  accent: string
  onSubmit: (text: string) => void
  onOpenPalette: () => void
  onValueChange?: (value: string) => void
  disabled?: boolean
}) {
  const [v, setV] = useState('')
  const taRef = useRef<HTMLTextAreaElement | null>(null)

  const updateValue = (next: string) => {
    setV(next)
    onValueChange?.(next)
  }

  const submit = () => {
    const t = v.trim()
    if (!t || disabled) return
    onSubmit(t)
    updateValue('')
    if (taRef.current) taRef.current.style.height = 'auto'
  }

  const keydown = (ev: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault()
      submit()
    } else if (ev.key === '/' && v === '') {
      ev.preventDefault()
      onOpenPalette()
    }
  }

  const autosize = (ev: React.ChangeEvent<HTMLTextAreaElement>) => {
    updateValue(ev.target.value)
    ev.target.style.height = 'auto'
    ev.target.style.height = Math.min(ev.target.scrollHeight, 200) + 'px'
  }

  const canSend = Boolean(v.trim()) && !disabled

  return (
    <div className="jr-pane" style={{ flexShrink: 0, background: theme.surface0 }}>
      <div className="jr-row" style={{ paddingTop: 0, paddingBottom: 10 }}>
        <label
          htmlFor="jarvis-composer"
          className="jr-gutter"
          style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.textDisabled }}
        >
          now
        </label>
        <div
          style={{
            borderTop: `1px solid ${theme.borderStrong}`,
            paddingTop: 10,
            display: 'flex',
            alignItems: 'flex-end',
            gap: 10,
          }}
        >
          <textarea
            id="jarvis-composer"
            ref={taRef}
            value={v}
            onChange={autosize}
            onKeyDown={keydown}
            rows={1}
            placeholder={
              disabled
                ? 'A turn is in flight…'
                : 'Message JARVIS… press / for agents, shift+⏎ for newline'
            }
            style={{
              all: 'unset',
              flex: 1,
              minWidth: 0,
              minHeight: 24,
              maxHeight: 200,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 14,
              lineHeight: 1.6,
              color: theme.textPrimary,
              resize: 'none',
              padding: '4px 0',
              whiteSpace: 'pre-wrap',
              overflowWrap: 'anywhere',
            }}
          />
          <button
            onClick={onOpenPalette}
            title="Commands (/ or ⌘K)"
            style={{
              all: 'unset',
              cursor: 'pointer',
              padding: '6px 4px',
              color: theme.textSecondary,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
            }}
          >
            / commands
          </button>
          <button
            onClick={submit}
            disabled={!canSend}
            style={{
              all: 'unset',
              cursor: canSend ? 'pointer' : 'default',
              padding: '6px 4px',
              color: canSend ? accent : theme.textDisabled,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            ⏎ send
          </button>
        </div>
      </div>
    </div>
  )
}
