// Shared pieces of the Journal look for the agent views: one row of the page
// grid from index.html (`.jr-row`), the section heading, and the styles for
// buttons, fields and prompt previews. Buttons are reset property by property
// instead of with `all: unset`, so the focus ring from index.html stays.

import type { CSSProperties, ReactNode } from 'react'

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

/** One row of the page: a gutter label, the reading column, and an optional
 *  margin note. `wide` lets the content run on through the margin, for an
 *  editor or a table that needs more than the reading column. */
export function JournalRow({
  theme,
  label,
  margin,
  wide,
  style,
  children,
}: {
  theme: Theme
  label?: ReactNode
  margin?: ReactNode
  wide?: boolean
  style?: CSSProperties
  children?: ReactNode
}) {
  return (
    <div className="jr-row" style={style}>
      <div
        className="jr-gutter"
        style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.textDisabled }}
      >
        {label}
      </div>
      <div style={{ minWidth: 0, color: theme.textPrimary, gridColumn: wide ? '2 / -1' : undefined }}>
        {children}
      </div>
      {margin && !wide ? (
        <div
          className="jr-margin"
          style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 12, color: theme.stats, minWidth: 0 }}
        >
          {margin}
        </div>
      ) : null}
    </div>
  )
}

/** A serif heading with a rule under it, as wide as the reading column. */
export function SectionHeading({ theme, children }: { theme: Theme; children: ReactNode }) {
  return (
    <h2
      style={{
        margin: 0,
        paddingBottom: 6,
        borderBottom: `1px solid ${theme.border}`,
        fontFamily: JARVIS_FONTS.serif,
        fontSize: 18,
        fontWeight: 600,
        lineHeight: 1.3,
        color: theme.textPrimary,
      }}
    >
      {children}
    </h2>
  )
}

/** Text meant to be read. Follows the reading face chosen in Tweaks: serif at
 *  `size`, or mono at 14px. */
export function readStyle(theme: Theme, size: number): CSSProperties {
  const serif = theme.read === JARVIS_FONTS.serif
  return { fontFamily: theme.read, fontSize: serif ? size : 14, lineHeight: 1.5 }
}

/** A line of metadata or status: loading, empty, error, counts. */
export function noteStyle(color: string): CSSProperties {
  return { fontFamily: JARVIS_FONTS.mono, fontSize: 13, lineHeight: 1.5, color }
}

const buttonBase: CSSProperties = {
  appearance: 'none',
  boxSizing: 'border-box',
  margin: 0,
  borderRadius: 4,
  fontFamily: JARVIS_FONTS.mono,
  fontSize: 13,
  lineHeight: 1.4,
  whiteSpace: 'nowrap',
}

/** The one filled button of a form: save, start session. */
export function primaryButton(theme: Theme, enabled = true): CSSProperties {
  return {
    ...buttonBase,
    padding: '8px 18px',
    border: '1px solid transparent',
    fontWeight: 600,
    background: enabled ? theme.textPrimary : theme.surface2,
    color: enabled ? theme.surface0 : theme.textDisabled,
    cursor: enabled ? 'pointer' : 'not-allowed',
  }
}

/** Every other button: revert, copy, restore, cancel. */
export function secondaryButton(theme: Theme, small = false): CSSProperties {
  return {
    ...buttonBase,
    padding: small ? '3px 12px' : '8px 18px',
    fontSize: small ? 12 : 13,
    border: `1px solid ${theme.borderStrong}`,
    background: 'transparent',
    color: theme.textPrimary,
    cursor: 'pointer',
  }
}

/** A button that reads as text: a tab, a name in a list, the way back. */
export function textButton(color: string): CSSProperties {
  return {
    appearance: 'none',
    margin: 0,
    padding: 0,
    border: 0,
    background: 'none',
    fontFamily: 'inherit',
    fontSize: 'inherit',
    fontWeight: 'inherit',
    lineHeight: 'inherit',
    textAlign: 'left',
    color,
    cursor: 'pointer',
  }
}

/** A textarea. The border darkens while it holds unsaved changes. */
export function fieldStyle(theme: Theme, changed = false): CSSProperties {
  return {
    display: 'block',
    width: '100%',
    boxSizing: 'border-box',
    padding: 14,
    border: `1px solid ${changed ? theme.textPrimary : theme.border}`,
    borderRadius: 4,
    background: theme.surface2,
    color: theme.textPrimary,
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 13,
    lineHeight: 1.55,
    resize: 'vertical',
  }
}

/** Prompt text that is shown, not edited: set off by a rule on the left, like
 *  the unfolded tool call in the chat stream. */
export function previewStyle(theme: Theme, maxHeight: number): CSSProperties {
  return {
    margin: 0,
    padding: '2px 0 2px 14px',
    borderLeft: `1px solid ${theme.borderStrong}`,
    fontFamily: JARVIS_FONTS.mono,
    fontSize: 13,
    lineHeight: 1.55,
    color: theme.textPrimary,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere',
    maxHeight,
    overflow: 'auto',
  }
}
