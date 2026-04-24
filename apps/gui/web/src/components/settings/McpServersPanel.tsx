// McpServersPanel — edits the dict[str, MCPServerSettings] at mcp.servers.
// Supports add/delete, transport-switched field sets, and renders
// model_validator errors (e.g. "stdio requires command") at the card header.

import { useState } from 'react'

import type { JsonSchemaNode, SettingsValidationError } from '../../lib/types'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

import {
  cardErrorsAt,
  fieldErrorAt,
  schemaAt,
  type Path,
} from './helpers'
import { SectionCardError } from './SectionCardError'
import { SettingField } from './SettingField'

type Transport = 'stdio' | 'sse' | 'streamable_http'

type ServerValue = {
  transport: Transport
  tool_group: string
  timeout_seconds: number
  command: string | null
  args: string[]
  env: Record<string, string> | null
  cwd: string | null
  url: string | null
  headers: Record<string, string> | null
}

function emptyServer(transport: Transport): ServerValue {
  return {
    transport,
    tool_group: '',
    timeout_seconds: 30,
    command: transport === 'stdio' ? '' : null,
    args: [],
    env: null,
    cwd: null,
    url: transport === 'stdio' ? null : '',
    headers: null,
  }
}

export function McpServersPanel({
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
  const section = (working['mcp'] as Record<string, unknown> | undefined) ?? {}
  const servers = (section['servers'] as Record<string, ServerValue> | undefined) ?? {}
  const enabled = section['enabled'] === true

  const mcpSchema = schemaAt(schema, ['mcp'])
  const serverSchema = schemaAt(mcpSchema, ['servers'])
  const singleServerSchema = (serverSchema?.['additionalProperties'] as JsonSchemaNode | undefined) ?? null

  const mcpLevelErrors = cardErrorsAt(errors, ['mcp'])

  const updateSection = (next: Record<string, unknown>) => {
    onChange({ ...working, mcp: next })
  }

  const setEnabled = (value: boolean) => {
    updateSection({ ...section, enabled: value })
  }

  const setServer = (name: string, value: ServerValue) => {
    updateSection({ ...section, servers: { ...servers, [name]: value } })
  }

  const deleteServer = (name: string) => {
    const next: Record<string, ServerValue> = { ...servers }
    delete next[name]
    updateSection({ ...section, servers: next })
  }

  const addServer = (name: string, transport: Transport) => {
    if (!name || name in servers) return
    updateSection({ ...section, servers: { ...servers, [name]: emptyServer(transport) } })
  }

  const renameServer = (oldName: string, newName: string) => {
    if (!newName || newName === oldName || newName in servers) return
    const entries = Object.entries(servers).map(([k, v]) => (k === oldName ? [newName, v] : [k, v]))
    updateSection({ ...section, servers: Object.fromEntries(entries) })
  }

  return (
    <div>
      <SettingField
        theme={theme}
        accent={accent}
        label="enabled"
        schema={schemaAt(mcpSchema, ['enabled'])}
        value={enabled}
        path={['mcp', 'enabled']}
        error={fieldErrorAt(errors, ['mcp', 'enabled'])}
        onChange={(next) => setEnabled(next === true)}
      />

      <SectionCardError theme={theme} errors={mcpLevelErrors} />

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
        servers ({Object.keys(servers).length})
      </div>

      {Object.entries(servers).map(([name, srv]) => (
        <ServerCard
          key={name}
          theme={theme}
          accent={accent}
          name={name}
          server={srv}
          schema={singleServerSchema}
          errors={errors}
          onRename={(next) => renameServer(name, next)}
          onChange={(next) => setServer(name, next)}
          onDelete={() => deleteServer(name)}
        />
      ))}

      <AddServerForm theme={theme} accent={accent} existing={Object.keys(servers)} onAdd={addServer} />
    </div>
  )
}

function ServerCard({
  theme,
  accent,
  name,
  server,
  schema,
  errors,
  onRename,
  onChange,
  onDelete,
}: {
  theme: Theme
  accent: string
  name: string
  server: ServerValue
  schema: JsonSchemaNode | null
  errors: SettingsValidationError[]
  onRename: (newName: string) => void
  onChange: (next: ServerValue) => void
  onDelete: () => void
}) {
  const cardPath: Path = ['mcp', 'servers', name]
  const cardErrors = cardErrorsAt(errors, cardPath)
  const [pendingName, setPendingName] = useState(name)

  const field = (key: keyof ServerValue, label: string) => {
    const abs: Path = [...cardPath, key]
    const err = fieldErrorAt(errors, abs)
    return (
      <SettingField
        theme={theme}
        accent={accent}
        label={label}
        schema={schemaAt(schema, [key])}
        value={server[key]}
        path={abs}
        error={err}
        onChange={(next) => onChange({ ...server, [key]: next } as ServerValue)}
      />
    )
  }

  return (
    <div
      style={{
        border: `1px solid ${cardErrors.length > 0 ? theme.error : theme.border}`,
        borderRadius: 6,
        padding: 14,
        marginBottom: 14,
        background: theme.surface1,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <input
          type="text"
          value={pendingName}
          onChange={(e) => setPendingName(e.target.value)}
          onBlur={() => {
            if (pendingName !== name) onRename(pendingName)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur()
          }}
          style={{
            flex: 1,
            padding: '5px 8px',
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 13,
            fontWeight: 600,
            color: theme.textPrimary,
            background: theme.surface0,
            border: `1px solid ${theme.border}`,
            borderRadius: 4,
            outline: 'none',
          }}
        />
        <button
          type="button"
          onClick={onDelete}
          style={{
            all: 'unset',
            cursor: 'pointer',
            padding: '5px 10px',
            borderRadius: 4,
            border: `1px solid ${theme.border}`,
            color: theme.textSecondary,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
          }}
        >
          delete
        </button>
      </div>

      <SectionCardError theme={theme} errors={cardErrors} />

      {field('transport', 'transport')}
      {field('tool_group', 'tool_group')}
      {field('timeout_seconds', 'timeout_seconds')}

      {server.transport === 'stdio' ? (
        <>
          {field('command', 'command')}
          <ListField
            theme={theme}
            accent={accent}
            label="args (one per line)"
            schema={schemaAt(schema, ['args'])}
            value={server.args}
            path={[...cardPath, 'args']}
            error={fieldErrorAt(errors, [...cardPath, 'args'])}
            onChange={(next) => onChange({ ...server, args: next })}
          />
          <DictField
            theme={theme}
            label="env"
            value={server.env}
            path={[...cardPath, 'env']}
            errors={errors}
            onChange={(next) => onChange({ ...server, env: next })}
          />
          {field('cwd', 'cwd')}
        </>
      ) : (
        <>
          {field('url', 'url')}
          <DictField
            theme={theme}
            label="headers"
            value={server.headers}
            path={[...cardPath, 'headers']}
            errors={errors}
            onChange={(next) => onChange({ ...server, headers: next })}
          />
        </>
      )}
    </div>
  )
}

function ListField({
  theme,
  accent,
  label,
  schema,
  value,
  path,
  error,
  onChange,
}: {
  theme: Theme
  accent: string
  label: string
  schema: JsonSchemaNode | null
  value: string[]
  path: Path
  error: string | null
  onChange: (next: string[]) => void
}) {
  return (
    <SettingField
      theme={theme}
      accent={accent}
      label={label}
      schema={schema}
      value={value}
      path={path}
      error={error}
      onChange={(next) => onChange(Array.isArray(next) ? (next as string[]) : [])}
    />
  )
}

function DictField({
  theme,
  label,
  value,
  path,
  errors,
  onChange,
}: {
  theme: Theme
  label: string
  value: Record<string, string> | null
  path: Path
  errors: SettingsValidationError[]
  onChange: (next: Record<string, string> | null) => void
}) {
  const entries = value ? Object.entries(value) : []
  const error = fieldErrorAt(errors, path)

  const update = (index: number, key: string, val: string) => {
    const next: Record<string, string> = {}
    entries.forEach(([k, v], i) => {
      if (i === index) {
        if (key) next[key] = val
      } else {
        next[k] = v
      }
    })
    onChange(Object.keys(next).length > 0 ? next : null)
  }

  const remove = (index: number) => {
    const next: Record<string, string> = {}
    entries.forEach(([k, v], i) => {
      if (i !== index) next[k] = v
    })
    onChange(Object.keys(next).length > 0 ? next : null)
  }

  const add = () => {
    const next: Record<string, string> = { ...(value ?? {}), '': '' }
    onChange(next)
  }

  return (
    <div style={{ marginBottom: 14 }}>
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color: theme.textSecondary,
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      {entries.map(([key, val], i) => (
        <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 4 }}>
          <input
            type="text"
            value={key}
            onChange={(e) => update(i, e.target.value, val)}
            placeholder="key"
            style={smallInput(theme)}
          />
          <input
            type="text"
            value={val}
            onChange={(e) => update(i, key, e.target.value)}
            placeholder="value"
            style={smallInput(theme)}
          />
          <button
            type="button"
            onClick={() => remove(i)}
            style={{
              all: 'unset',
              cursor: 'pointer',
              padding: '4px 8px',
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
      ))}
      <button
        type="button"
        onClick={add}
        style={{
          all: 'unset',
          cursor: 'pointer',
          padding: '5px 10px',
          borderRadius: 4,
          border: `1px dashed ${theme.border}`,
          color: theme.textSecondary,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          marginTop: 2,
        }}
      >
        + add entry
      </button>
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

function smallInput(theme: Theme): React.CSSProperties {
  return {
    flex: 1,
    padding: '5px 8px',
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 11,
    color: theme.textPrimary,
    background: theme.surface0,
    border: `1px solid ${theme.border}`,
    borderRadius: 4,
    outline: 'none',
  }
}

function AddServerForm({
  theme,
  accent,
  existing,
  onAdd,
}: {
  theme: Theme
  accent: string
  existing: string[]
  onAdd: (name: string, transport: Transport) => void
}) {
  const [name, setName] = useState('')
  const [transport, setTransport] = useState<Transport>('stdio')
  const nameValid = name.length > 0 && !name.includes('__') && !existing.includes(name)

  return (
    <div
      style={{
        borderTop: `1px dashed ${theme.border}`,
        paddingTop: 16,
        marginTop: 8,
      }}
    >
      <div
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color: theme.textSecondary,
          marginBottom: 8,
        }}
      >
        add server
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="name (no __)"
          style={{
            flex: 1,
            padding: '6px 10px',
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textPrimary,
            background: theme.surface1,
            border: `1px solid ${theme.border}`,
            borderRadius: 4,
            outline: 'none',
          }}
        />
        <select
          value={transport}
          onChange={(e) => setTransport(e.target.value as Transport)}
          style={{
            padding: '6px 10px',
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textPrimary,
            background: theme.surface1,
            border: `1px solid ${theme.border}`,
            borderRadius: 4,
          }}
        >
          <option value="stdio">stdio</option>
          <option value="sse">sse</option>
          <option value="streamable_http">streamable_http</option>
        </select>
        <button
          type="button"
          disabled={!nameValid}
          onClick={() => {
            onAdd(name, transport)
            setName('')
          }}
          style={{
            all: 'unset',
            cursor: nameValid ? 'pointer' : 'not-allowed',
            padding: '6px 14px',
            borderRadius: 4,
            background: nameValid ? accent : theme.surface2,
            color: nameValid ? theme.surface0 : theme.textDisabled,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          add
        </button>
      </div>
    </div>
  )
}
