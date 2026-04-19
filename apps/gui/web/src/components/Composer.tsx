import { useRef, useState } from 'react'

import { JARVIS_FONTS, type Theme } from '../lib/tokens'

export function Composer({
  theme,
  accent,
  onSubmit,
  onOpenPalette,
  disabled,
}: {
  theme: Theme
  accent: string
  onSubmit: (text: string) => void
  onOpenPalette: () => void
  disabled?: boolean
}) {
  const [v, setV] = useState('')
  const taRef = useRef<HTMLTextAreaElement | null>(null)

  const submit = () => {
    const t = v.trim()
    if (!t || disabled) return
    onSubmit(t)
    setV('')
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
    setV(ev.target.value)
    ev.target.style.height = 'auto'
    ev.target.style.height = Math.min(ev.target.scrollHeight, 200) + 'px'
  }

  return (
    <div
      style={{
        padding: '12px 24px 16px',
        borderTop: `1px solid ${theme.border}`,
        background: theme.surface0,
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '96px 1fr',
          gap: 16,
          alignItems: 'start',
        }}
      >
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.user,
            fontWeight: 700,
            paddingTop: 10,
          }}
        >
          You:
        </div>
        <div
          style={{
            background: theme.surface1,
            border: `1px solid ${theme.border}`,
            borderRadius: 10,
            padding: '8px 10px',
            display: 'flex',
            alignItems: 'flex-end',
            gap: 8,
          }}
          onFocusCapture={(ev) => (ev.currentTarget.style.borderColor = accent)}
          onBlurCapture={(ev) => (ev.currentTarget.style.borderColor = theme.border)}
        >
          <button
            onClick={onOpenPalette}
            title="Commands (/ or ⌘K)"
            style={{
              all: 'unset',
              cursor: 'pointer',
              padding: '6px 8px',
              borderRadius: 6,
              color: theme.textDisabled,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
            }}
          >
            /
          </button>
          <textarea
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
              minHeight: 24,
              maxHeight: 200,
              fontFamily: JARVIS_FONTS.sans,
              fontSize: 15,
              lineHeight: 1.55,
              color: theme.textPrimary,
              resize: 'none',
              padding: '4px 0',
            }}
          />
          <button
            onClick={submit}
            disabled={!v.trim() || disabled}
            style={{
              all: 'unset',
              cursor: v.trim() && !disabled ? 'pointer' : 'default',
              padding: '6px 10px',
              borderRadius: 6,
              background: v.trim() && !disabled ? accent : 'transparent',
              color: v.trim() && !disabled ? theme.surface1 : theme.textDisabled,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            ⏎ send
          </button>
        </div>
      </div>
    </div>
  )
}
