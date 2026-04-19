import { JARVIS_FONTS, type Theme } from '../lib/tokens'

export function Stub({ theme, name }: { theme: Theme; name: string }) {
  return (
    <main
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 12,
        background: theme.surface0,
      }}
    >
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 14,
          color: theme.textSecondary,
        }}
      >
        {name}
      </div>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color: theme.textDisabled,
        }}
      >
        Coming in a later phase. Use the Chat view for now.
      </div>
    </main>
  )
}
