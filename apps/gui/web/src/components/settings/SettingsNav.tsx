// SettingsNav — the list of sections on the left: plain text links, the current
// one underlined, with a dot for customised sections and for validation errors.

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { SettingsValidationError } from '../../lib/types'

import { sectionHasErrors } from './helpers'
import { SECTIONS, type SectionKey } from './sections'
import { buttonReset } from './SettingField'

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
      aria-label="Settings sections"
      style={{
        width: 180,
        borderRight: `1px solid ${theme.border}`,
        padding: '28px 0 20px',
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
            aria-current={isActive ? 'page' : undefined}
            style={{
              ...buttonReset,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
              boxSizing: 'border-box',
              padding: '6px 20px 6px 28px',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
              color: hasError
                ? theme.error
                : isActive
                  ? theme.textPrimary
                  : theme.textSecondary,
            }}
          >
            <span
              style={{
                flex: 1,
                textDecoration: isActive ? 'underline' : 'none',
                textUnderlineOffset: 4,
              }}
            >
              {section.label}
            </span>
            {hasError ? (
              <span
                role="img"
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
                role="img"
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: theme.textSecondary,
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
