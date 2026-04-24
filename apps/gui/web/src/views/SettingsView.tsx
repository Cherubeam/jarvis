// SettingsView — 2-pane settings editor. Left nav + right panel + sticky footer.
//
// Fetches GET /api/settings + /api/settings/schema; holds an `original` snapshot
// and a `working` copy of the settings dict. Panels edit `working` through
// helpers in components/settings/helpers.ts. Save PUTs the full working state;
// 409 → managed-header overwrite dialog; 422 → normalised errors attached to
// fields (inline) or cards (headers). No in-process reload — response carries
// `restart_required: true` and the footer says so.

import { useEffect, useMemo, useState } from 'react'

import { FilesystemPanel } from '../components/settings/FilesystemPanel'
import { McpServersPanel } from '../components/settings/McpServersPanel'
import { ObsidianPanel } from '../components/settings/ObsidianPanel'
import { PatternCardsPanel } from '../components/settings/PatternCardsPanel'
import { PanelHeader, PanelWarning, ScalarPanel } from '../components/settings/ScalarPanel'
import { deepEqual } from '../components/settings/helpers'
import {
  OverwriteDialog,
  SettingsFooter,
  type SaveStatus,
} from '../components/settings/SettingsShell'
import { SettingsNav } from '../components/settings/SettingsNav'
import { SCALAR_SECTIONS, SECTION_SUBTITLES } from '../components/settings/scalarSections'
import { SECTIONS, type SectionKey } from '../components/settings/sections'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type {
  JsonSchemaNode,
  PutSettingsResult,
  SettingsResponse,
  SettingsValidationError,
} from '../lib/types'

export function SettingsView({
  theme,
  accent,
}: {
  theme: Theme
  accent: string
}) {
  const [data, setData] = useState<SettingsResponse | null>(null)
  const [schema, setSchema] = useState<JsonSchemaNode | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [working, setWorking] = useState<Record<string, unknown> | null>(null)
  const [active, setActive] = useState<SectionKey>('models')
  const [status, setStatus] = useState<SaveStatus>({ kind: 'idle' })
  const [errors, setErrors] = useState<SettingsValidationError[]>([])
  const [pendingOverwrite, setPendingOverwrite] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    const ac = new AbortController()
    setLoadError(null)
    Promise.all([
      fetch('/api/settings', { signal: ac.signal }).then((r) =>
        r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)),
      ),
      fetch('/api/settings/schema', { signal: ac.signal }).then((r) =>
        r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)),
      ),
    ])
      .then(([settings, sch]: [SettingsResponse, JsonSchemaNode]) => {
        setData(settings)
        setSchema(sch)
        setWorking(settings.settings as Record<string, unknown>)
      })
      .catch((e) => {
        if ((e as { name?: string })?.name !== 'AbortError') {
          setLoadError((e as Error).message || String(e))
        }
      })
    return () => ac.abort()
  }, [])

  const overrides = data?.overrides ?? {}
  const isDirty = useMemo(
    () => !!data && !!working && !deepEqual(working, data.settings),
    [working, data],
  )

  const discard = () => {
    if (!data) return
    setWorking(data.settings as Record<string, unknown>)
    setErrors([])
    setStatus({ kind: 'idle' })
  }

  const doSave = async (payload: Record<string, unknown>, acceptOverwrite: boolean) => {
    setStatus({ kind: 'saving' })
    setErrors([])
    try {
      const r = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: payload, accept_overwrite: acceptOverwrite }),
      })
      if (r.status === 409 && !acceptOverwrite) {
        setPendingOverwrite(payload)
        setStatus({ kind: 'needs_overwrite' })
        return
      }
      if (r.status === 422) {
        const body = await r.json()
        const detail = body?.detail as SettingsValidationError[] | undefined
        setErrors(detail ?? [])
        setStatus({
          kind: 'error',
          message: `${detail?.length ?? 0} validation error(s)`,
        })
        if (detail && detail.length > 0) {
          const firstSection = (detail[0].loc[0] ?? detail[0].card_loc[0]) as SectionKey | undefined
          if (firstSection && SECTIONS.some((s) => s.key === firstSection)) setActive(firstSection)
        }
        return
      }
      if (!r.ok) {
        const text = await r.text()
        throw new Error(`HTTP ${r.status}: ${text}`)
      }
      const result = (await r.json()) as PutSettingsResult
      // Refresh the original snapshot from the same payload (server diffs it);
      // overrides come back from the server.
      setData((prev) =>
        prev
          ? {
              ...prev,
              settings: payload,
              overrides: result.overrides,
              local_yaml_has_managed_header: true,
            }
          : prev,
      )
      setStatus({ kind: 'saved' })
    } catch (e) {
      setStatus({ kind: 'error', message: (e as Error).message || String(e) })
    }
  }

  const save = () => {
    if (!working) return
    void doSave(working, false)
  }

  const confirmOverwrite = () => {
    if (!pendingOverwrite) return
    const payload = pendingOverwrite
    setPendingOverwrite(null)
    void doSave(payload, true)
  }

  return (
    <main style={{ flex: 1, display: 'flex', minWidth: 0, background: theme.surface0 }}>
      {loadError && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.error,
          }}
        >
          failed to load settings: {loadError}
        </div>
      )}

      {!loadError && !data && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textDisabled,
          }}
        >
          loading settings…
        </div>
      )}

      {data && working && (
        <>
          <SettingsNav
            theme={theme}
            accent={accent}
            active={active}
            setActive={setActive}
            overrides={overrides}
            errors={errors}
          />
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              minWidth: 0,
            }}
          >
            <div
              style={{
                flex: 1,
                overflow: 'auto',
                padding: '28px 32px 40px',
              }}
            >
              <PanelHeader
                theme={theme}
                title={SECTIONS.find((s) => s.key === active)?.label ?? active}
                subtitle={SECTION_SUBTITLES[active]}
              />
              {renderActivePanel({
                active,
                theme,
                accent,
                working,
                schema,
                errors,
                setWorking,
              })}
            </div>
            <SettingsFooter
              theme={theme}
              accent={accent}
              isDirty={isDirty}
              status={status}
              onSave={save}
              onDiscard={discard}
            />
          </div>

          {pendingOverwrite && (
            <OverwriteDialog
              theme={theme}
              accent={accent}
              localYamlPath={data.paths.local_yaml}
              onConfirm={confirmOverwrite}
              onCancel={() => {
                setPendingOverwrite(null)
                setStatus({ kind: 'idle' })
              }}
            />
          )}
        </>
      )}
    </main>
  )
}

function renderActivePanel({
  active,
  theme,
  accent,
  working,
  schema,
  errors,
  setWorking,
}: {
  active: SectionKey
  theme: Theme
  accent: string
  working: Record<string, unknown>
  schema: JsonSchemaNode | null
  errors: SettingsValidationError[]
  setWorking: (next: Record<string, unknown>) => void
}) {
  if (active === 'obsidian') {
    return (
      <ObsidianPanel
        theme={theme}
        accent={accent}
        working={working}
        schema={schema}
        errors={errors}
        onChange={setWorking}
      />
    )
  }
  if (active === 'pattern_cards') {
    return (
      <PatternCardsPanel
        theme={theme}
        accent={accent}
        working={working}
        schema={schema}
        errors={errors}
        onChange={setWorking}
      />
    )
  }
  if (active === 'mcp') {
    return (
      <McpServersPanel
        theme={theme}
        accent={accent}
        working={working}
        schema={schema}
        errors={errors}
        onChange={setWorking}
      />
    )
  }
  if (active === 'filesystem') {
    return (
      <FilesystemPanel
        theme={theme}
        accent={accent}
        working={working}
        schema={schema}
        errors={errors}
        onChange={setWorking}
      />
    )
  }
  const fields = SCALAR_SECTIONS[active]
  if (!fields) return null

  const banner =
    active === 'paths' ? (
      <PanelWarning
        theme={theme}
        text="Changing these paths while JARVIS is running can leave data inconsistent. Stop the CLI and GUI before editing, then restart."
      />
    ) : null

  return (
    <ScalarPanel
      theme={theme}
      accent={accent}
      sectionKey={active}
      fields={fields}
      working={working}
      schema={schema}
      errors={errors}
      onChange={setWorking}
      banner={banner}
    />
  )
}
