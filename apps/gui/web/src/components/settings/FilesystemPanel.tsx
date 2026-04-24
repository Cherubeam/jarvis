// FilesystemPanel — edits the list[AccessRuleSettings] at filesystem.access_rules.

import type { JsonSchemaNode, SettingsValidationError } from '../../lib/types'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

import { fieldErrorAt, schemaAt, type Path } from './helpers'

type AccessLevel = 'deny' | 'read' | 'write' | 'read-write'
const ACCESS_CHOICES: AccessLevel[] = ['deny', 'read', 'write', 'read-write']

type Rule = { path: string; access: AccessLevel }

export function FilesystemPanel({
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
  const section = (working['filesystem'] as Record<string, unknown> | undefined) ?? {}
  const rules = (section['access_rules'] as Rule[] | undefined) ?? []
  const rulesSchema = schemaAt(schema, ['filesystem', 'access_rules'])
  const _ruleSchema = rulesSchema?.['items'] as JsonSchemaNode | undefined
  void _ruleSchema

  const update = (next: Rule[]) => {
    onChange({ ...working, filesystem: { ...section, access_rules: next } })
  }

  const setRule = (i: number, rule: Rule) => {
    const next = [...rules]
    next[i] = rule
    update(next)
  }

  const addRule = () => {
    update([...rules, { path: '', access: 'read' }])
  }

  const removeRule = (i: number) => {
    update(rules.filter((_, j) => j !== i))
  }

  return (
    <div>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color: theme.textSecondary,
          marginBottom: 10,
          lineHeight: 1.55,
        }}
      >
        Per-path access rules enforced by FilesystemGuard. Most-specific path
        wins; missing paths default to deny.
      </div>

      {rules.map((rule, i) => {
        const pathErr = fieldErrorAt(errors, ['filesystem', 'access_rules', i, 'path'])
        const accessErr = fieldErrorAt(errors, ['filesystem', 'access_rules', i, 'access'])
        return (
          <div
            key={i}
            style={{
              display: 'flex',
              gap: 6,
              marginBottom: 6,
              padding: 10,
              background: theme.surface1,
              border: `1px solid ${pathErr || accessErr ? theme.error : theme.border}`,
              borderRadius: 4,
              alignItems: 'flex-start',
            }}
          >
            <div style={{ flex: 1 }}>
              <input
                type="text"
                value={rule.path}
                onChange={(e) => setRule(i, { ...rule, path: e.target.value })}
                placeholder="/absolute/path"
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '6px 10px',
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                  color: theme.textPrimary,
                  background: theme.surface0,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 4,
                  outline: 'none',
                }}
              />
              {pathErr && (
                <div
                  style={{
                    marginTop: 2,
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 10,
                    color: theme.error,
                  }}
                >
                  {pathErr}
                </div>
              )}
            </div>
            <div>
              <select
                value={rule.access}
                onChange={(e) => setRule(i, { ...rule, access: e.target.value as AccessLevel })}
                style={{
                  padding: '6px 10px',
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                  color: theme.textPrimary,
                  background: theme.surface0,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 4,
                  minWidth: 110,
                }}
              >
                {ACCESS_CHOICES.map((choice) => (
                  <option key={choice} value={choice}>
                    {choice}
                  </option>
                ))}
              </select>
              {accessErr && (
                <div
                  style={{
                    marginTop: 2,
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 10,
                    color: theme.error,
                  }}
                >
                  {accessErr}
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => removeRule(i)}
              style={{
                all: 'unset',
                cursor: 'pointer',
                padding: '6px 10px',
                borderRadius: 4,
                border: `1px solid ${theme.border}`,
                color: theme.textSecondary,
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 10,
              }}
            >
              ×
            </button>
          </div>
        )
      })}

      <button
        type="button"
        onClick={addRule}
        style={{
          all: 'unset',
          cursor: 'pointer',
          padding: '7px 14px',
          borderRadius: 4,
          border: `1px dashed ${theme.border}`,
          color: accent,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          marginTop: 4,
        }}
      >
        + add rule
      </button>
    </div>
  )
}
