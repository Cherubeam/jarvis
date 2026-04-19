import { Icon } from '../Icon'
import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { DiffLine } from '../../lib/types'
import { Row } from './Row'

export function ApprovalEvent({
  e,
  theme,
  onApprove,
  onReject,
  dense,
}: {
  e: { id: string; tool: string; agent: string; path: string; diff: DiffLine[]; summary: string }
  theme: Theme
  onApprove: () => void
  onReject: () => void
  dense?: boolean
}) {
  return (
    <Row theme={theme} label="approve" labelColor={theme.system} mono dense={dense}>
      <div
        style={{
          background: theme.surface2,
          border: `1px solid ${theme.system}40`,
          borderLeft: `3px solid ${theme.system}`,
          borderRadius: 8,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '10px 14px',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            borderBottom: `1px solid ${theme.border}`,
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 13,
          }}
        >
          <Icon name="note" size={14} color={theme.system} />
          <div style={{ color: theme.textPrimary, fontWeight: 600 }}>{e.tool}</div>
          <div style={{ color: theme.assistant }}>{e.path}</div>
          <div style={{ marginLeft: 'auto', color: theme.textSecondary, fontSize: 12 }}>
            {e.summary}
          </div>
        </div>
        <div
          style={{
            maxHeight: 280,
            overflow: 'auto',
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12.5,
            lineHeight: 1.55,
          }}
        >
          {e.diff.map((line, i) => {
            const bg =
              line.kind === 'add'
                ? `${theme.user}1a`
                : line.kind === 'del'
                ? `${theme.error}1a`
                : 'transparent'
            const fg =
              line.kind === 'add' ? theme.user : line.kind === 'del' ? theme.error : theme.textSecondary
            const glyph = line.kind === 'add' ? '+ ' : line.kind === 'del' ? '- ' : '  '
            return (
              <div key={i} style={{ background: bg, padding: '1px 14px', color: fg }}>
                <span style={{ opacity: 0.6, userSelect: 'none' }}>{glyph}</span>
                {line.text || '\u00A0'}
              </div>
            )
          })}
        </div>
        <div
          style={{
            display: 'flex',
            gap: 8,
            padding: '10px 14px',
            borderTop: `1px solid ${theme.border}`,
          }}
        >
          <button
            onClick={onApprove}
            style={{
              all: 'unset',
              cursor: 'pointer',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              padding: '6px 14px',
              borderRadius: 6,
              background: theme.user,
              color: theme.surface1,
              fontWeight: 700,
            }}
          >
            Approve (⏎)
          </button>
          <button
            onClick={onReject}
            style={{
              all: 'unset',
              cursor: 'pointer',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              padding: '6px 14px',
              borderRadius: 6,
              border: `1px solid ${theme.border}`,
              color: theme.textSecondary,
            }}
          >
            Reject (esc)
          </button>
          <div
            style={{
              marginLeft: 'auto',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 11,
              color: theme.textDisabled,
              alignSelf: 'center',
            }}
          >
            {e.agent} · vault_write
          </div>
        </div>
      </div>
    </Row>
  )
}
