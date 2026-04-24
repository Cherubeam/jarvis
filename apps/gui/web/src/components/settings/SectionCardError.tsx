// SectionCardError — red banner for @model_validator failures that don't
// attach to a single field (e.g. MCP stdio server missing `command`).

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { SettingsValidationError } from '../../lib/types'

export function SectionCardError({
  theme,
  errors,
}: {
  theme: Theme
  errors: SettingsValidationError[]
}) {
  if (errors.length === 0) return null
  return (
    <div
      style={{
        borderLeft: `3px solid ${theme.error}`,
        background: theme.surface1,
        padding: '8px 12px',
        marginBottom: 12,
        borderRadius: 4,
      }}
    >
      {errors.map((err, i) => (
        <div
          key={i}
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: theme.error,
            lineHeight: 1.45,
          }}
        >
          {err.msg}
        </div>
      ))}
    </div>
  )
}
