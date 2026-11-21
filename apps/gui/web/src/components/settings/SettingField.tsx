// SettingField — one form row. Renders a label, the field's description as a
// line of reading text, an input appropriate for the scalar type, and an inline
// error under the input.
//
// Also the home of the shared control styles for the settings panels (inputs,
// buttons, labels), so every panel draws the same Journal controls.

import { useId } from 'react'

import type { JsonSchemaNode } from '../../lib/types'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

import {
  enumChoices,
  fieldDescription,
  fieldType,
  type Path,
} from './helpers'

/** Reset for a real <button> that keeps the global focus ring (`all: unset`
 *  as an inline style would switch it off). */
export const buttonReset: React.CSSProperties = {
  appearance: 'none',
  margin: 0,
  padding: 0,
  border: 0,
  background: 'transparent',
  font: 'inherit',
  color: 'inherit',
  textAlign: 'left',
  cursor: 'pointer',
}

export function inputStyle(theme: Theme, hasError = false): React.CSSProperties {
  return {
    width: '100%',
    boxSizing: 'border-box',
    minHeight: 36,
    padding: '7px 12px',
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 13,
    lineHeight: 1.5,
    color: theme.textPrimary,
    background: theme.surface2,
    border: `1px solid ${hasError ? theme.error : theme.border}`,
    borderRadius: 4,
  }
}

export function primaryButtonStyle(theme: Theme, enabled = true): React.CSSProperties {
  return {
    ...buttonReset,
    cursor: enabled ? 'pointer' : 'not-allowed',
    padding: '9px 18px',
    borderRadius: 4,
    background: enabled ? theme.textPrimary : theme.surface3,
    color: enabled ? theme.surface0 : theme.textDisabled,
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 13,
    fontWeight: 600,
    textAlign: 'center',
  }
}

export function secondaryButtonStyle(theme: Theme, enabled = true): React.CSSProperties {
  return {
    ...buttonReset,
    cursor: enabled ? 'pointer' : 'not-allowed',
    padding: '8px 18px',
    borderRadius: 4,
    border: `1px solid ${enabled ? theme.borderStrong : theme.border}`,
    color: enabled ? theme.textPrimary : theme.textDisabled,
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 13,
    textAlign: 'center',
  }
}

export function fieldLabelStyle(theme: Theme): React.CSSProperties {
  return {
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 13,
    color: theme.textSecondary,
  }
}

export function fieldErrorStyle(theme: Theme): React.CSSProperties {
  return {
    marginTop: 4,
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 12,
    color: theme.error,
  }
}

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
  const id = useId()
  const labelId = `${id}-label`
  const descId = description ? `${id}-desc` : undefined

  const descriptionLine = description ? (
    <div
      id={descId}
      style={{
        fontFamily: theme.read,
        fontSize: 15,
        lineHeight: 1.45,
        color: theme.textSecondary,
      }}
    >
      {description}
    </div>
  ) : null

  const errorLine = error ? <div style={fieldErrorStyle(theme)}>{error}</div> : null

  // A switch reads as one line: the switch, then what it switches.
  if (kind === 'bool') {
    return (
      <div style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, minHeight: 36 }}>
          <Toggle
            theme={theme}
            accent={accent}
            value={value === true}
            onChange={onChange}
            labelledBy={labelId}
            describedBy={descId}
          />
          <span
            id={labelId}
            style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 13, color: theme.textPrimary }}
          >
            {label}
          </span>
        </div>
        {descriptionLine}
        {errorLine}
      </div>
    )
  }

  return (
    <div style={{ marginBottom: 18 }}>
      <label
        id={labelId}
        htmlFor={kind === 'enum' ? undefined : id}
        style={{ ...fieldLabelStyle(theme), display: 'block' }}
      >
        {label}
      </label>
      {descriptionLine}
      <div style={{ marginTop: 6 }}>
        {renderInput({
          kind,
          theme,
          schema,
          value,
          onChange,
          id,
          labelId,
          descId,
          hasError: Boolean(error),
        })}
      </div>
      {errorLine}
    </div>
  )
}

function renderInput({
  kind,
  theme,
  schema,
  value,
  onChange,
  id,
  labelId,
  descId,
  hasError,
}: {
  kind: ReturnType<typeof fieldType>
  theme: Theme
  schema: JsonSchemaNode | null
  value: unknown
  onChange: (next: unknown) => void
  id: string
  labelId: string
  descId: string | undefined
  hasError: boolean
}) {
  if (kind === 'enum') {
    const choices = enumChoices(schema)
    return (
      <SegmentedControl
        theme={theme}
        value={typeof value === 'string' ? value : ''}
        choices={choices}
        onChange={onChange}
        labelledBy={labelId}
        describedBy={descId}
      />
    )
  }
  if (kind === 'int' || kind === 'float') {
    return (
      <input
        id={id}
        type="number"
        step={kind === 'int' ? 1 : 'any'}
        value={value == null ? '' : String(value)}
        aria-describedby={descId}
        aria-invalid={hasError || undefined}
        onChange={(e) => {
          const raw = e.target.value
          if (raw === '') {
            onChange(null)
            return
          }
          const parsed = kind === 'int' ? parseInt(raw, 10) : parseFloat(raw)
          onChange(Number.isFinite(parsed) ? parsed : raw)
        }}
        style={inputStyle(theme, hasError)}
      />
    )
  }
  if (kind === 'list_string') {
    const joined = Array.isArray(value) ? (value as string[]).join('\n') : ''
    return (
      <textarea
        id={id}
        value={joined}
        aria-describedby={descId}
        aria-invalid={hasError || undefined}
        onChange={(e) => {
          const lines = e.target.value
            .split('\n')
            .map((s) => s.trim())
            .filter((s) => s.length > 0)
          onChange(lines)
        }}
        rows={Math.max(3, (Array.isArray(value) ? value.length : 0) + 1)}
        style={{ ...inputStyle(theme, hasError), display: 'block', resize: 'vertical' }}
      />
    )
  }
  // string | unknown
  return (
    <input
      id={id}
      type="text"
      value={value == null ? '' : String(value)}
      aria-describedby={descId}
      aria-invalid={hasError || undefined}
      onChange={(e) => onChange(e.target.value)}
      style={inputStyle(theme, hasError)}
    />
  )
}

function Toggle({
  theme,
  accent,
  value,
  onChange,
  labelledBy,
  describedBy,
}: {
  theme: Theme
  accent: string
  value: boolean
  onChange: (next: boolean) => void
  labelledBy: string
  describedBy: string | undefined
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      style={{
        ...buttonReset,
        flexShrink: 0,
        boxSizing: 'content-box',
        width: 38,
        height: 20,
        borderRadius: 999,
        background: value ? accent : theme.surface2,
        border: `1px solid ${value ? accent : theme.borderStrong}`,
        position: 'relative',
        display: 'inline-block',
      }}
      aria-pressed={value}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
    >
      <span
        style={{
          position: 'absolute',
          top: 3,
          left: value ? 21 : 3,
          width: 14,
          height: 14,
          borderRadius: '50%',
          background: value ? theme.surface0 : theme.textSecondary,
          transition: 'left 120ms ease',
        }}
      />
    </button>
  )
}

function SegmentedControl({
  theme,
  value,
  choices,
  onChange,
  labelledBy,
  describedBy,
}: {
  theme: Theme
  value: string
  choices: string[]
  onChange: (next: string) => void
  labelledBy: string
  describedBy: string | undefined
}) {
  return (
    <div
      role="group"
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      style={{ display: 'flex', gap: '4px 20px', flexWrap: 'wrap', minHeight: 36, alignItems: 'center' }}
    >
      {choices.map((choice) => {
        const active = choice === value
        return (
          <button
            type="button"
            key={choice}
            onClick={() => onChange(choice)}
            aria-pressed={active}
            style={{
              ...buttonReset,
              padding: '6px 0',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
              color: active ? theme.textPrimary : theme.textSecondary,
              textDecoration: active ? 'underline' : 'none',
              textUnderlineOffset: 4,
            }}
          >
            {choice}
          </button>
        )
      })}
    </div>
  )
}
