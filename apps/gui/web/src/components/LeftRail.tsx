import { Icon } from './Icon'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'

// Top-level rail keys. 'agent' (detail, singular) is a sub-view of 'agents' and
// has no rail slot — App.tsx maps it back to 'agents' before passing to LeftRail
// so the Agents button stays highlighted on the detail page.
export type ViewKey = 'chat' | 'home' | 'agents' | 'agent' | 'history' | 'settings'

const ITEMS: { key: ViewKey; label: string; icon: string }[] = [
  { key: 'home', label: 'Home', icon: 'sparkle' },
  { key: 'chat', label: 'Chat', icon: 'terminal' },
  { key: 'agents', label: 'Agents', icon: 'tool' },
  { key: 'history', label: 'History', icon: 'history' },
]

const BOTTOM: { key: ViewKey; label: string; icon: string }[] = [
  { key: 'settings', label: 'Settings', icon: 'note' },
]

export function LeftRail({
  theme,
  accent,
  view,
  setView,
}: {
  theme: Theme
  accent: string
  view: ViewKey
  setView: (v: ViewKey) => void
}) {
  const item = (it: { key: ViewKey; label: string; icon: string }) => {
    const active = view === it.key
    return (
      <button
        key={it.key}
        title={it.label}
        onClick={() => setView(it.key)}
        style={{
          all: 'unset',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 56,
          height: 48,
          color: active ? accent : theme.textDisabled,
          borderLeft: active ? `2px solid ${accent}` : '2px solid transparent',
          background: active ? theme.surface2 : 'transparent',
          fontFamily: JARVIS_FONTS.mono,
        }}
      >
        <Icon name={it.icon} size={18} />
      </button>
    )
  }
  return (
    <aside
      style={{
        width: 56,
        flexShrink: 0,
        background: theme.surface1,
        borderRight: `1px solid ${theme.border}`,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div style={{ flex: 1 }}>{ITEMS.map(item)}</div>
      <div>{BOTTOM.map(item)}</div>
    </aside>
  )
}
