// SettingsShell — sticky save/discard footer + post-save banner + 409 overwrite dialog.

import { JARVIS_FONTS, JARVIS_MEASURE, type Theme } from '../../lib/tokens'

import { primaryButtonStyle, secondaryButtonStyle } from './SettingField'

export type SaveStatus =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | {
      kind: 'saved'
      restart_required: boolean
      hot_applied_fields: string[]
      restart_required_fields: string[]
    }
  | { kind: 'needs_overwrite' }
  | { kind: 'error'; message: string }

function savedMessage(status: Extract<SaveStatus, { kind: 'saved' }>): string {
  const { hot_applied_fields, restart_required_fields } = status
  if (hot_applied_fields.length === 0 && restart_required_fields.length === 0) {
    return 'saved to config/local.yaml · no changes'
  }
  if (restart_required_fields.length === 0) {
    const suffix = hot_applied_fields.length === 1 ? '' : 's'
    return `saved · ${hot_applied_fields.length} change${suffix} applied live`
  }
  if (hot_applied_fields.length === 0) {
    const suffix = restart_required_fields.length === 1 ? '' : 's'
    return `saved · restart JARVIS for ${restart_required_fields.length} change${suffix} to take effect`
  }
  const restartSuffix = restart_required_fields.length === 1 ? '' : 's'
  return (
    `saved · ${hot_applied_fields.length} applied live · ` +
    `restart for ${restart_required_fields.length} more change${restartSuffix}`
  )
}

export function SettingsFooter({
  theme,
  isDirty,
  status,
  onSave,
  onDiscard,
}: {
  theme: Theme
  accent: string
  isDirty: boolean
  status: SaveStatus
  onSave: () => void
  onDiscard: () => void
}) {
  const saving = status.kind === 'saving'
  const canSave = isDirty && !saving
  const canDiscard = isDirty && !saving
  return (
    <div
      style={{
        position: 'sticky',
        bottom: 0,
        padding: '14px 40px',
        background: theme.surface0,
        borderTop: `1px solid ${theme.border}`,
      }}
    >
      <div
        style={{
          maxWidth: JARVIS_MEASURE.column,
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '8px 10px',
        }}
      >
        <button
          type="button"
          onClick={onSave}
          disabled={!canSave}
          style={primaryButtonStyle(theme, canSave)}
        >
          {saving ? 'saving…' : 'save'}
        </button>
        <button
          type="button"
          onClick={onDiscard}
          disabled={!canDiscard}
          style={secondaryButtonStyle(theme, canDiscard)}
        >
          discard
        </button>
        <div
          role="status"
          style={{
            flex: '1 1 200px',
            minWidth: 0,
            marginLeft: 6,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            lineHeight: 1.5,
            color:
              status.kind === 'error'
                ? theme.error
                : status.kind === 'saved'
                  ? theme.textPrimary
                  : theme.textSecondary,
          }}
        >
          {status.kind === 'idle' && isDirty && 'unsaved changes'}
          {status.kind === 'saving' && 'saving…'}
          {status.kind === 'saved' && savedMessage(status)}
          {status.kind === 'error' && `error: ${status.message}`}
          {status.kind === 'needs_overwrite' && 'config/local.yaml was hand-edited — confirm to overwrite'}
        </div>
      </div>
    </div>
  )
}

export function OverwriteDialog({
  theme,
  localYamlPath,
  onConfirm,
  onCancel,
}: {
  theme: Theme
  accent: string
  localYamlPath: string
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-overwrite-title"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
      }}
    >
      <div
        style={{
          background: theme.surface1,
          border: `1px solid ${theme.borderStrong}`,
          borderRadius: 6,
          padding: 24,
          maxWidth: 520,
          boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
        }}
      >
        <h2
          id="settings-overwrite-title"
          style={{
            margin: '0 0 10px',
            fontFamily: JARVIS_FONTS.serif,
            fontSize: 20,
            fontWeight: 600,
            lineHeight: 1.3,
            color: theme.textPrimary,
          }}
        >
          Overwrite hand-edited file?
        </h2>
        <div
          style={{
            fontFamily: theme.read,
            fontSize: 15,
            color: theme.textSecondary,
            lineHeight: 1.55,
            marginBottom: 20,
          }}
        >
          <code style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 13, wordBreak: 'break-word' }}>
            {localYamlPath}
          </code>{' '}
          doesn't start with the JARVIS Settings
          managed header. Saving will rewrite it — only the customised fields
          visible in this GUI will be preserved. Any hand-added comments or
          fields outside the Settings schema will be lost.
          <div style={{ marginTop: 10, color: theme.textPrimary }}>
            If you have work-in-progress YAML here, back it up before continuing.
          </div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'flex-end', gap: 10 }}>
          <button type="button" onClick={onCancel} style={secondaryButtonStyle(theme)}>
            cancel
          </button>
          <button type="button" onClick={onConfirm} style={primaryButtonStyle(theme)}>
            overwrite
          </button>
        </div>
      </div>
    </div>
  )
}
