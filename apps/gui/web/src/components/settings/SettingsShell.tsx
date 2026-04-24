// SettingsShell — sticky save/discard footer + post-save banner + 409 overwrite dialog.

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

export type SaveStatus =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'saved' }
  | { kind: 'needs_overwrite' }
  | { kind: 'error'; message: string }

export function SettingsFooter({
  theme,
  accent,
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
  return (
    <div
      style={{
        position: 'sticky',
        bottom: 0,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '12px 28px',
        background: theme.surface0,
        borderTop: `1px solid ${theme.border}`,
      }}
    >
      <div
        style={{
          flex: 1,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          color:
            status.kind === 'error'
              ? theme.error
              : status.kind === 'saved'
                ? accent
                : theme.textSecondary,
        }}
      >
        {status.kind === 'idle' && isDirty && 'unsaved changes'}
        {status.kind === 'saving' && 'saving…'}
        {status.kind === 'saved' &&
          'saved to config/local.yaml · restart JARVIS for changes to take effect'}
        {status.kind === 'error' && `error: ${status.message}`}
        {status.kind === 'needs_overwrite' && 'config/local.yaml was hand-edited — confirm to overwrite'}
      </div>
      <button
        type="button"
        onClick={onDiscard}
        disabled={!isDirty || saving}
        style={{
          all: 'unset',
          cursor: isDirty && !saving ? 'pointer' : 'not-allowed',
          padding: '7px 14px',
          borderRadius: 4,
          border: `1px solid ${theme.border}`,
          color: isDirty && !saving ? theme.textSecondary : theme.textDisabled,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
        }}
      >
        discard
      </button>
      <button
        type="button"
        onClick={onSave}
        disabled={!canSave}
        style={{
          all: 'unset',
          cursor: canSave ? 'pointer' : 'not-allowed',
          padding: '7px 16px',
          borderRadius: 4,
          background: canSave ? accent : theme.surface2,
          color: canSave ? theme.surface0 : theme.textDisabled,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: 0.3,
        }}
      >
        {saving ? 'saving…' : 'save'}
      </button>
    </div>
  )
}

export function OverwriteDialog({
  theme,
  accent,
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
          border: `1px solid ${theme.border}`,
          borderRadius: 8,
          padding: 24,
          maxWidth: 520,
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}
      >
        <div
          style={{
            fontFamily: JARVIS_FONTS.sans,
            fontSize: 16,
            fontWeight: 600,
            color: theme.textPrimary,
            marginBottom: 10,
          }}
        >
          Overwrite hand-edited file?
        </div>
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textSecondary,
            lineHeight: 1.55,
            marginBottom: 18,
          }}
        >
          <code>{localYamlPath}</code> doesn't start with the JARVIS Settings
          managed header. Saving will rewrite it — only the customised fields
          visible in this GUI will be preserved. Any hand-added comments or
          fields outside the Settings schema will be lost.
          <div style={{ marginTop: 10, color: theme.textPrimary }}>
            If you have work-in-progress YAML here, back it up before continuing.
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button
            type="button"
            onClick={onCancel}
            style={{
              all: 'unset',
              cursor: 'pointer',
              padding: '8px 16px',
              borderRadius: 4,
              border: `1px solid ${theme.border}`,
              color: theme.textSecondary,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
            }}
          >
            cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            style={{
              all: 'unset',
              cursor: 'pointer',
              padding: '8px 16px',
              borderRadius: 4,
              background: accent,
              color: theme.surface0,
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 0.3,
            }}
          >
            overwrite
          </button>
        </div>
      </div>
    </div>
  )
}
