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
    <div
      style={{
        marginBottom: 24,
        paddingBottom: 14,
        borderBottom: `1px solid ${theme.border}`,
      }}
    >
      <h1
        style={{
          margin: 0,
          fontFamily: JARVIS_FONTS.serif,
          fontSize: 28,
          fontWeight: 600,
          lineHeight: 1.2,
          color: theme.textPrimary,
        }}
      >
        {title}
      </h1>
      {subtitle && (
        <p
          style={{
            margin: '6px 0 0',
            fontFamily: theme.read,
            fontSize: 16,
            lineHeight: 1.5,
            color: theme.textSecondary,
          }}
        >
          {subtitle}
        </p>
      )}
    </div>
  )
}

/** A heading for a group of fields inside a panel. `rule` draws a line under
 *  it; leave it off when the first thing below already starts with a rule. */
export function SubSectionHeader({
  theme,
  rule = true,
  children,
}: {
  theme: Theme
  rule?: boolean
  children: React.ReactNode
}) {
  return (
    <h2
      style={{
        margin: '30px 0 16px',
        paddingBottom: rule ? 8 : 0,
        borderBottom: rule ? `1px solid ${theme.border}` : 'none',
        fontFamily: JARVIS_FONTS.serif,
        fontSize: 18,
        fontWeight: 600,
        lineHeight: 1.3,
        color: theme.textPrimary,
      }}
    >
      {children}
    </h2>
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
        background: theme.delBg,
        padding: '10px 14px',
        marginBottom: 20,
        borderRadius: 4,
        fontFamily: theme.read,
        fontSize: 15,
        color: theme.del,
        lineHeight: 1.5,
      }}
    >
      {text}
    </div>
  )
}
