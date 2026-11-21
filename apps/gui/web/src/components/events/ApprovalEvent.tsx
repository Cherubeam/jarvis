import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { DiffLine } from '../../lib/types'
import { Row } from './Row'

/** A vault write waiting for a decision. Set off by a rule above and below
 *  instead of a box; the file path leads, the diff follows, the two buttons
 *  close it. Who asked and the change summary sit in the margin. */
export function ApprovalEvent({
  e,
  theme,
  onApprove,
  onReject,
  dense,
}: {
  e: { id: string; tool: string; agent: string; path: string; diff: DiffLine[]; summary: string; linkWarnings?: string[] }
  theme: Theme
  onApprove: () => void
  onReject: () => void
  dense?: boolean
}) {
  return (
    <Row
      theme={theme}
      label=""
      dense={dense}
      margin={
        <div style={{ paddingTop: 10 }}>
          <div>waits for you</div>
          <div>{e.agent} · vault_write</div>
          <div>{e.summary}</div>
        </div>
      }
    >
      <section
        aria-label="Vault write waiting for approval"
        style={{
          borderTop: `1px solid ${theme.textPrimary}`,
          borderBottom: `1px solid ${theme.border}`,
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 13,
        }}
      >
        <div style={{ padding: '10px 0 8px', wordBreak: 'break-word' }}>
          <span style={{ color: theme.textSecondary }}>{e.tool} · </span>
          {e.path}
        </div>
        {e.linkWarnings && e.linkWarnings.length > 0 && (
          <div style={{ padding: '6px 10px', marginBottom: 8, background: theme.delBg, color: theme.del, fontSize: 12.5 }}>
            <div style={{ fontWeight: 600 }}>Links changed — check these before approving:</div>
            {e.linkWarnings.map((w, i) => (
              <div key={i} style={{ wordBreak: 'break-word' }}>
                {w}
              </div>
            ))}
          </div>
        )}
        <div style={{ maxHeight: 280, overflow: 'auto', fontSize: 12.5, lineHeight: 1.55 }}>
          {e.diff.map((line, i) => {
            const bg = line.kind === 'add' ? theme.addBg : line.kind === 'del' ? theme.delBg : 'transparent'
            const fg = line.kind === 'add' ? theme.add : line.kind === 'del' ? theme.del : theme.textSecondary
            const glyph = line.kind === 'add' ? '+ ' : line.kind === 'del' ? '- ' : '  '
            return (
              <div key={i} style={{ background: bg, padding: '1px 10px', color: fg, whiteSpace: 'pre-wrap' }}>
                <span style={{ userSelect: 'none' }}>{glyph}</span>
                {line.text || ' '}
              </div>
            )
          })}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, padding: '14px 0' }}>
          <button
            onClick={onApprove}
            style={{
              all: 'unset',
              cursor: 'pointer',
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
              fontWeight: 600,
              padding: '9px 18px',
              borderRadius: 4,
              background: theme.textPrimary,
              color: theme.surface0,
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
              fontSize: 13,
              padding: '8px 18px',
              borderRadius: 4,
              border: `1px solid ${theme.borderStrong}`,
              color: theme.textPrimary,
            }}
          >
            Reject (esc)
          </button>
        </div>
      </section>
    </Row>
  )
}
