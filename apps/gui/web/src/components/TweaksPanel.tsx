import { Icon } from './Icon'
import { ACCENT_HUES, type AccentKey, JARVIS_FONTS, type Theme } from '../lib/tokens'

export type Tweaks = {
  mode: 'dark' | 'light'
  sidebar: boolean
  sidebarMode: 'list' | 'timeline'
  density: 'comfortable' | 'compact'
  toolStyle: 'card' | 'inline' | 'dim'
  showStats: boolean
  /** Typeface of the assistant's answers. */
  reading: 'serif' | 'mono'
  accent: AccentKey
}

export const DEFAULT_TWEAKS: Tweaks = {
  mode: 'dark',
  sidebar: true,
  sidebarMode: 'list',
  density: 'comfortable',
  toolStyle: 'card',
  showStats: true,
  reading: 'serif',
  accent: 'blue',
}

export function TweaksPanel({
  theme,
  open,
  tweaks,
  setTweak,
  onClose,
}: {
  theme: Theme
  open: boolean
  tweaks: Tweaks
  setTweak: <K extends keyof Tweaks>(k: K, v: Tweaks[K]) => void
  onClose: () => void
}) {
  if (!open) return null
  const row = (label: string, children: React.ReactNode) => (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '120px 1fr',
        alignItems: 'center',
        gap: 10,
        padding: '8px 0',
      }}
    >
      <div style={{ fontSize: 12, color: theme.textSecondary }}>{label}</div>
      <div>{children}</div>
    </div>
  )
  const seg = <K extends keyof Tweaks>(k: K, opts: { v: Tweaks[K]; l: string }[]) => (
    <div
      style={{
        display: 'inline-flex',
        background: theme.surface2,
        borderRadius: 6,
        padding: 2,
      }}
    >
      {opts.map((o) => (
        <button
          key={String(o.v)}
          onClick={() => setTweak(k, o.v)}
          style={{
            all: 'unset',
            cursor: 'pointer',
            padding: '4px 10px',
            borderRadius: 4,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            background: tweaks[k] === o.v ? theme.surface3 : 'transparent',
            color: tweaks[k] === o.v ? theme.textPrimary : theme.textSecondary,
          }}
        >
          {o.l}
        </button>
      ))}
    </div>
  )
  return (
    <div
      style={{
        position: 'absolute',
        right: 16,
        top: 16,
        width: 320,
        zIndex: 20,
        background: theme.surface1,
        border: `1px solid ${theme.borderStrong}`,
        borderRadius: 6,
        boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          borderBottom: `1px solid ${theme.border}`,
        }}
      >
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textSecondary,
          }}
        >
          Tweaks
        </div>
        <button
          onClick={onClose}
          aria-label="Close tweaks"
          style={{ all: 'unset', cursor: 'pointer', marginLeft: 'auto', color: theme.textSecondary }}
        >
          <Icon name="close" size={12} />
        </button>
      </div>
      <div style={{ padding: '8px 14px 14px' }}>
        {row('mode', seg('mode', [{ v: 'dark', l: 'dark' }, { v: 'light', l: 'light' }]))}
        {row('sidebar', seg('sidebar', [{ v: true, l: 'on' }, { v: false, l: 'off' }]))}
        {row(
          'sidebar mode',
          seg('sidebarMode', [
            { v: 'list', l: 'list' },
            { v: 'timeline', l: 'timeline' },
          ]),
        )}
        {row(
          'density',
          seg('density', [
            { v: 'comfortable', l: 'comfortable' },
            { v: 'compact', l: 'compact' },
          ]),
        )}
        {row(
          'tool style',
          seg('toolStyle', [
            { v: 'card', l: 'unfold' },
            { v: 'inline', l: 'line' },
            { v: 'dim', l: 'dim' },
          ]),
        )}
        {row('stats', seg('showStats', [{ v: true, l: 'show' }, { v: false, l: 'hide' }]))}
        {row(
          'answers',
          seg('reading', [
            { v: 'serif', l: 'serif' },
            { v: 'mono', l: 'mono' },
          ]),
        )}
        {row(
          'accent',
          <div style={{ display: 'flex', gap: 6 }}>
            {(Object.entries(ACCENT_HUES) as [AccentKey, { dark: string; light: string }][]).map(
              ([k, v]) => (
                <button
                  key={k}
                  onClick={() => setTweak('accent', k)}
                  title={k}
                  aria-label={`Accent ${k}`}
                  style={{
                    all: 'unset',
                    cursor: 'pointer',
                    width: 22,
                    height: 22,
                    borderRadius: '50%',
                    background: theme.surface0 === '#FFFFFF' ? v.light : v.dark,
                    outline: tweaks.accent === k ? `2px solid ${theme.textPrimary}` : 'none',
                    outlineOffset: 2,
                  }}
                />
              ),
            )}
          </div>,
        )}
      </div>
    </div>
  )
}
