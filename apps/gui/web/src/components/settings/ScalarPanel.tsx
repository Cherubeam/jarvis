// ScalarPanel — renders a list of SettingField rows for a section's leaf fields.
// Used by the 12 sections without dynamic collections or deeply-nested models.

import type { JsonSchemaNode, SettingsValidationError } from '../../lib/types'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

import {
  fieldErrorAt,
  getAt,
  schemaAt,
  setAt,
  type Path,
} from './helpers'
import { SettingField } from './SettingField'

export type FieldSpec = {
  path: Path // relative to the section root (e.g. ["presets", "fast"])
  label: string
}

export function ScalarPanel({
  theme,
  accent,
  sectionKey,
  fields,
  working,
  schema,
  errors,
  onChange,
  banner,
  footer,
}: {
  theme: Theme
  accent: string
  sectionKey: string
  fields: FieldSpec[]
  working: Record<string, unknown>
  schema: JsonSchemaNode | null
  errors: SettingsValidationError[]
  onChange: (next: Record<string, unknown>) => void
  banner?: React.ReactNode
  footer?: React.ReactNode
}) {
  const sectionValue = (working[sectionKey] as Record<string, unknown> | undefined) ?? {}
  const sectionSchema = schemaAt(schema, [sectionKey])

  const update = (relPath: Path, value: unknown) => {
    const nextSection = setAt(sectionValue, relPath, value) as Record<string, unknown>
    onChange({ ...working, [sectionKey]: nextSection })
  }

  return (
    <div>
      {banner}
      {fields.map((field) => {
        const absPath: Path = [sectionKey, ...field.path]
        const relSchema = schemaAt(sectionSchema, field.path)
        const value = getAt(sectionValue, field.path)
        const error = fieldErrorAt(errors, absPath)
        return (
          <SettingField
            key={field.path.join('.')}
            theme={theme}
            accent={accent}
            label={field.label}
            schema={relSchema}
            value={value}
            path={absPath}
            error={error}
            onChange={(next) => update(field.path, next)}
          />
        )
      })}
      {footer}
    </div>
  )
}

export function PanelHeader({
  theme,
  title,
  subtitle,
}: {
  theme: Theme
  title: string
  subtitle?: string
}) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div
        style={{
          fontFamily: JARVIS_FONTS.sans,
          fontSize: 18,
          fontWeight: 600,
          color: theme.textPrimary,
          letterSpacing: -0.2,
        }}
      >
        {title}
      </div>
      {subtitle && (
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            color: theme.textSecondary,
            marginTop: 4,
          }}
        >
          {subtitle}
        </div>
      )}
    </div>
  )
}

export function PanelWarning({
  theme,
  text,
}: {
  theme: Theme
  text: string
}) {
  return (
    <div
      style={{
        borderLeft: `3px solid ${theme.error}`,
        background: theme.surface1,
        padding: '8px 12px',
        marginBottom: 14,
        borderRadius: 4,
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 11,
        color: theme.textSecondary,
        lineHeight: 1.55,
      }}
    >
      {text}
    </div>
  )
}
