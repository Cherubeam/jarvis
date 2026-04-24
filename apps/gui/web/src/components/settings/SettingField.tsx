// SettingField — one form row. Renders a label + hover-tooltip (description),
// an input appropriate for the scalar type, and an inline error under the input.

import type { JsonSchemaNode } from '../../lib/types'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

import {
  enumChoices,
  fieldDescription,
  fieldType,
  type Path,
} from './helpers'

export function SettingField({
  theme,
  accent,
  label,
  schema,
  value,
  onChange,
  error,
  path: _path,
}: {
  theme: Theme
  accent: string
  label: string
  schema: JsonSchemaNode | null
  value: unknown
  onChange: (next: unknown) => void
  error: string | null
  path: Path
}) {
  const kind = fieldType(schema)
  const description = fieldDescription(schema)

  return (
    <div style={{ marginBottom: 14 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color: theme.textSecondary,
          marginBottom: 4,
        }}
      >
        <span>{label}</span>
        {description && (
          <span
            title={description}
            aria-label={description}
            style={{
              fontSize: 10,
              color: theme.textDisabled,
              cursor: 'help',
              borderRadius: 999,
              border: `1px solid ${theme.border}`,
              width: 14,
              height: 14,
              lineHeight: '12px',
              textAlign: 'center',
            }}
          >
            ?
          </span>
        )}
      </div>
      {renderInput({ kind, theme, accent, schema, value, onChange })}
      {error && (
        <div
          style={{
            marginTop: 4,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 10,
            color: theme.error,
          }}
        >
          {error}
        </div>
      )}
    </div>
  )
}

function renderInput({
  kind,
  theme,
  accent,
  schema,
  value,
  onChange,
}: {
  kind: ReturnType<typeof fieldType>
  theme: Theme
  accent: string
  schema: JsonSchemaNode | null
  value: unknown
  onChange: (next: unknown) => void
}) {
  if (kind === 'bool') {
    return <Toggle theme={theme} accent={accent} value={value === true} onChange={onChange} />
  }
  if (kind === 'enum') {
    const choices = enumChoices(schema)
    return (
      <SegmentedControl
        theme={theme}
        accent={accent}
        value={typeof value === 'string' ? value : ''}
        choices={choices}
        onChange={onChange}
      />
    )
  }
  if (kind === 'int' || kind === 'float') {
    return (
      <input
        type="number"
        step={kind === 'int' ? 1 : 'any'}
        value={value == null ? '' : String(value)}
        onChange={(e) => {
          const raw = e.target.value
          if (raw === '') {
            onChange(null)
            return
          }
          const parsed = kind === 'int' ? parseInt(raw, 10) : parseFloat(raw)
          onChange(Number.isFinite(parsed) ? parsed : raw)
        }}
        style={inputStyle(theme)}
      />
    )
  }
  if (kind === 'list_string') {
    const joined = Array.isArray(value) ? (value as string[]).join('\n') : ''
    return (
      <textarea
        value={joined}
        onChange={(e) => {
          const lines = e.target.value
            .split('\n')
            .map((s) => s.trim())
            .filter((s) => s.length > 0)
          onChange(lines)
        }}
        rows={Math.max(3, (Array.isArray(value) ? value.length : 0) + 1)}
        style={{ ...inputStyle(theme), resize: 'vertical' }}
      />
    )
  }
  // string | unknown
  return (
    <input
      type="text"
      value={value == null ? '' : String(value)}
      onChange={(e) => onChange(e.target.value)}
      style={inputStyle(theme)}
    />
  )
}

function inputStyle(theme: Theme): React.CSSProperties {
  return {
    width: '100%',
    boxSizing: 'border-box',
    padding: '7px 10px',
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 12,
    color: theme.textPrimary,
    background: theme.surface1,
    border: `1px solid ${theme.border}`,
    borderRadius: 4,
    outline: 'none',
  }
}

function Toggle({
  theme,
  accent,
  value,
  onChange,
}: {
  theme: Theme
  accent: string
  value: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      style={{
        all: 'unset',
        cursor: 'pointer',
        width: 38,
        height: 20,
        borderRadius: 999,
        background: value ? accent : theme.surface2,
        border: `1px solid ${value ? accent : theme.border}`,
        position: 'relative',
        display: 'inline-block',
      }}
      aria-pressed={value}
    >
      <span
        style={{
          position: 'absolute',
          top: 2,
          left: value ? 20 : 2,
          width: 14,
          height: 14,
          borderRadius: '50%',
          background: theme.surface0,
          transition: 'left 120ms ease',
        }}
      />
    </button>
  )
}

function SegmentedControl({
  theme,
  accent,
  value,
  choices,
  onChange,
}: {
  theme: Theme
  accent: string
  value: string
  choices: string[]
  onChange: (next: string) => void
}) {
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {choices.map((choice) => {
        const active = choice === value
        return (
          <button
            type="button"
            key={choice}
            onClick={() => onChange(choice)}
            style={{
              all: 'unset',
              cursor: 'pointer',
              padding: '5px 10px',
              borderRadius: 4,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              color: active ? accent : theme.textSecondary,
              border: `1px solid ${active ? accent : theme.border}`,
              background: active ? theme.surface2 : 'transparent',
            }}
          >
            {choice}
          </button>
        )
      })}
    </div>
  )
}
