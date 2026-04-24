// ObsidianPanel — exposes the nested daily_notes + writing sub-models.

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

type FieldSpec = { path: Path; label: string }

const ROOT_FIELDS: FieldSpec[] = [
  { path: ['enabled'], label: 'enabled' },
  { path: ['vault_path'], label: 'vault_path' },
  { path: ['prompts_dir'], label: 'prompts_dir' },
]

const DAILY_FIELDS: FieldSpec[] = [
  { path: ['daily_notes', 'path_format'], label: 'daily_notes.path_format' },
]

const WRITING_FIELDS: FieldSpec[] = [
  { path: ['writing', 'blog_dir'], label: 'writing.blog_dir' },
  { path: ['writing', 'template_path'], label: 'writing.template_path' },
  { path: ['writing', 'patterns', 'target_dir'], label: 'writing.patterns.target_dir' },
  { path: ['writing', 'patterns', 'template_path'], label: 'writing.patterns.template_path' },
  { path: ['writing', 'slip_box', 'target_dir'], label: 'writing.slip_box.target_dir' },
  { path: ['writing', 'slip_box', 'template_path'], label: 'writing.slip_box.template_path' },
]

export function ObsidianPanel({
  theme,
  accent,
  working,
  schema,
  errors,
  onChange,
}: {
  theme: Theme
  accent: string
  working: Record<string, unknown>
  schema: JsonSchemaNode | null
  errors: SettingsValidationError[]
  onChange: (next: Record<string, unknown>) => void
}) {
  const section = (working['obsidian'] as Record<string, unknown> | undefined) ?? {}
  const sectionSchema = schemaAt(schema, ['obsidian'])

  const update = (relPath: Path, value: unknown) => {
    const nextSection = setAt(section, relPath, value) as Record<string, unknown>
    onChange({ ...working, obsidian: nextSection })
  }

  const renderRow = (spec: FieldSpec) => {
    const abs: Path = ['obsidian', ...spec.path]
    const value = getAt(section, spec.path)
    const err = fieldErrorAt(errors, abs)
    return (
      <SettingField
        key={spec.path.join('.')}
        theme={theme}
        accent={accent}
        label={spec.label}
        schema={schemaAt(sectionSchema, spec.path)}
        value={value}
        path={abs}
        error={err}
        onChange={(next) => update(spec.path, next)}
      />
    )
  }

  return (
    <div>
      {ROOT_FIELDS.map(renderRow)}

      <SubSectionHeader theme={theme} text="daily notes" />
      {DAILY_FIELDS.map(renderRow)}

      <SubSectionHeader theme={theme} text="writing targets" />
      {WRITING_FIELDS.map(renderRow)}
    </div>
  )
}

function SubSectionHeader({ theme, text }: { theme: Theme; text: string }) {
  return (
    <div
      style={{
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 11,
        fontWeight: 600,
        color: theme.textSecondary,
        textTransform: 'uppercase',
        letterSpacing: 0.8,
        marginTop: 18,
        marginBottom: 10,
        paddingBottom: 6,
        borderBottom: `1px solid ${theme.border}`,
      }}
    >
      {text}
    </div>
  )
}
