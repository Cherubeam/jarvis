// PatternCardsPanel — output_dir + nested image_generation.

import type { JsonSchemaNode, SettingsValidationError } from '../../lib/types'
import type { Theme } from '../../lib/tokens'

import { fieldErrorAt, getAt, schemaAt, setAt, type Path } from './helpers'
import { SubSectionHeader } from './ScalarPanel'
import { SettingField } from './SettingField'

type FieldSpec = { path: Path; label: string }

const ROOT_FIELDS: FieldSpec[] = [
  { path: ['output_dir'], label: 'output_dir' },
]

const IMG_FIELDS: FieldSpec[] = [
  { path: ['image_generation', 'enabled'], label: 'image_generation.enabled' },
  { path: ['image_generation', 'model'], label: 'image_generation.model' },
  { path: ['image_generation', 'size'], label: 'image_generation.size (WxH)' },
  { path: ['image_generation', 'max_images_per_run'], label: 'image_generation.max_images_per_run' },
]

export function PatternCardsPanel({
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
  const section = (working['pattern_cards'] as Record<string, unknown> | undefined) ?? {}
  const sectionSchema = schemaAt(schema, ['pattern_cards'])

  const update = (relPath: Path, value: unknown) => {
    const nextSection = setAt(section, relPath, value) as Record<string, unknown>
    onChange({ ...working, pattern_cards: nextSection })
  }

  const renderRow = (spec: FieldSpec) => {
    const abs: Path = ['pattern_cards', ...spec.path]
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

      <SubSectionHeader theme={theme}>image generation</SubSectionHeader>
      {IMG_FIELDS.map(renderRow)}
    </div>
  )
}
