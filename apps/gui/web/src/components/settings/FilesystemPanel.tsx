// FilesystemPanel — edits the list[AccessRuleSettings] at filesystem.access_rules.
// One line per rule: path, access level, remove.

import type { JsonSchemaNode, SettingsValidationError } from '../../lib/types'
import type { Theme } from '../../lib/tokens'

import { fieldErrorAt, schemaAt, type Path } from './helpers'
import { fieldErrorStyle, inputStyle, secondaryButtonStyle } from './SettingField'

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
      <p
        style={{
          margin: '0 0 20px',
          fontFamily: theme.read,
          fontSize: 15,
          color: theme.textSecondary,
          lineHeight: 1.5,
        }}
      >
        Per-path access rules enforced by FilesystemGuard. Most-specific path
        wins; missing paths default to deny.
      </p>

      {rules.map((rule, i) => {
        const pathErr = fieldErrorAt(errors, ['filesystem', 'access_rules', i, 'path'])
        const accessErr = fieldErrorAt(errors, ['filesystem', 'access_rules', i, 'access'])
        return (
          <div
            key={i}
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 8,
              marginBottom: 8,
              alignItems: 'flex-start',
            }}
          >
            <div style={{ flex: '1 1 220px', minWidth: 0 }}>
              <input
                type="text"
                aria-label="path"
                aria-invalid={Boolean(pathErr) || undefined}
                value={rule.path}
                onChange={(e) => setRule(i, { ...rule, path: e.target.value })}
                placeholder="/absolute/path"
                style={inputStyle(theme, Boolean(pathErr))}
              />
              {pathErr && <div style={fieldErrorStyle(theme)}>{pathErr}</div>}
            </div>
            <div>
              <select
                aria-label="access"
                aria-invalid={Boolean(accessErr) || undefined}
                value={rule.access}
                onChange={(e) => setRule(i, { ...rule, access: e.target.value as AccessLevel })}
                style={{ ...inputStyle(theme, Boolean(accessErr)), width: 'auto', minWidth: 130 }}
              >
                {ACCESS_CHOICES.map((choice) => (
                  <option key={choice} value={choice}>
                    {choice}
                  </option>
                ))}
              </select>
              {accessErr && <div style={fieldErrorStyle(theme)}>{accessErr}</div>}
            </div>
            <button
              type="button"
              onClick={() => removeRule(i)}
              aria-label="remove rule"
              style={{ ...secondaryButtonStyle(theme), padding: '8px 12px' }}
            >
              ×
            </button>
          </div>
        )
      })}

      <button
        type="button"
        onClick={addRule}
        style={{ ...secondaryButtonStyle(theme), marginTop: 6 }}
      >
        + add rule
      </button>
    </div>
  )
}
