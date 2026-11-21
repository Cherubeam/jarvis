import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

/** The page title: the greeting in the reading face, the date under it. */
export function GreetingHeader({
  theme,
  greeting,
  dayLabel,
}: {
  theme: Theme
  greeting: string
  dayLabel: string
}) {
  return (
    <div style={{ paddingBottom: 8 }}>
      <h1
        style={{
          margin: 0,
          fontFamily: JARVIS_FONTS.serif,
          fontSize: 32,
          fontWeight: 600,
          color: theme.textPrimary,
          lineHeight: 1.2,
        }}
      >
        {greeting}.
      </h1>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
          lineHeight: 1.5,
          color: theme.textSecondary,
          marginTop: 8,
        }}
      >
        {dayLabel}
      </div>
    </div>
  )
}
