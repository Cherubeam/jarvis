import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

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
    <div style={{ marginBottom: 36 }}>
      <div
        style={{
          fontFamily: JARVIS_FONTS.sans,
          fontSize: 28,
          fontWeight: 600,
          color: theme.textPrimary,
          letterSpacing: -0.4,
          lineHeight: 1.2,
        }}
      >
        {greeting}.
      </div>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: theme.textSecondary,
          marginTop: 6,
          letterSpacing: 0.2,
        }}
      >
        {dayLabel}
      </div>
    </div>
  )
}
