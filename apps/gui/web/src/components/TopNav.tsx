import { JARVIS_FONTS, type Theme } from '../lib/tokens'

// Top-level view keys. 'agent' (detail, singular) is a sub-view of 'agents' and
// has no nav slot — App.tsx maps it back to 'agents' before passing to TopNav
// so the Agents link stays marked on the detail page.
export type ViewKey =
  | 'chat'
  | 'home'
  | 'agents'
  | 'agent'
  | 'outcomes'
  | 'history'
  | 'settings'

const ITEMS: { key: ViewKey; label: string }[] = [
  { key: 'home', label: 'Home' },
  { key: 'chat', label: 'Chat' },
  { key: 'agents', label: 'Agents' },
  { key: 'outcomes', label: 'Outcomes' },
  { key: 'history', label: 'History' },
  { key: 'settings', label: 'Settings' },
]

/** One line of words across the top. Replaces the icon rail: a word says where
 *  it goes, an icon has to be learned. */
export function TopNav({
  theme,
  view,
  setView,
}: {
  theme: Theme
  view: ViewKey
  setView: (v: ViewKey) => void
}) {
  return (
    <header
      style={{
        flexShrink: 0,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: '4px 22px',
        padding: '12px 28px',
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 13,
      }}
    >
      <span style={{ fontWeight: 600, color: theme.textPrimary }}>JARVIS</span>
      <nav aria-label="Sections" style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 18px' }}>
        {ITEMS.map((it) => {
          const active = view === it.key
          return (
            <button
              key={it.key}
              onClick={() => setView(it.key)}
              aria-current={active ? 'page' : undefined}
              style={{
                all: 'unset',
                cursor: 'pointer',
                padding: '4px 0',
                color: active ? theme.textPrimary : theme.textSecondary,
                textDecoration: active ? 'underline' : 'none',
                textUnderlineOffset: 4,
              }}
            >
              {it.label}
            </button>
          )
        })}
      </nav>
    </header>
  )
}
