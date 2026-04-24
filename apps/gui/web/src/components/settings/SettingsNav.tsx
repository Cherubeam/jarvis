// SettingsNav — left-rail section picker with customised dots + error dots.

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { SettingsValidationError } from '../../lib/types'

import { sectionHasErrors } from './helpers'
import { SECTIONS, type SectionKey } from './sections'

export function SettingsNav({
  theme,
  accent,
  active,
  setActive,
  overrides,
  errors,
}: {
  theme: Theme
  accent: string
  active: SectionKey
  setActive: (key: SectionKey) => void
  overrides: Record<string, unknown>
  errors: SettingsValidationError[]
}) {
  return (
    <nav
      style={{
        width: 180,
        borderRight: `1px solid ${theme.border}`,
        padding: '16px 0',
        overflowY: 'auto',
        flexShrink: 0,
        background: theme.surface0,
      }}
    >
      {SECTIONS.map((section) => {
        const isActive = section.key === active
        const isCustomized = section.key in overrides
        const hasError = sectionHasErrors(errors, section.key)
        return (
          <button
            key={section.key}
            type="button"
            onClick={() => setActive(section.key)}
            style={{
              all: 'unset',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
              boxSizing: 'border-box',
              padding: '7px 16px 7px 20px',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: hasError
                ? theme.error
                : isActive
                  ? theme.textPrimary
                  : theme.textSecondary,
              background: isActive ? theme.surface1 : 'transparent',
              borderLeft: isActive ? `2px solid ${accent}` : '2px solid transparent',
              fontWeight: isActive ? 600 : 400,
            }}
          >
            <span style={{ flex: 1 }}>{section.label}</span>
            {hasError ? (
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: theme.error,
                }}
                aria-label="has validation error"
              />
            ) : isCustomized ? (
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: accent,
                  opacity: 0.75,
                }}
                aria-label="customized"
              />
            ) : null}
          </button>
        )
      })}
    </nav>
  )
}
