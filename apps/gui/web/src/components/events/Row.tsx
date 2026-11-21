import type { ReactNode } from 'react'

import { JARVIS_FONTS, type Theme } from '../../lib/tokens'

/** One entry in the stream, laid out like a journal page: a gutter on the left
 *  (the time of a turn, or who is speaking), the reading column, and an optional
 *  margin note on the right. The grid lives in index.html (`.jr-row`). */
export function Row({
  theme,
  label,
  labelColor,
  dense,
  margin,
  children,
}: {
  theme: Theme
  label: string
  labelColor?: string
  dense?: boolean
  margin?: ReactNode
  children: ReactNode
}) {
  return (
    <div className={dense ? 'jr-row dense' : 'jr-row'}>
      <div
        className="jr-gutter"
        style={{
          fontFamily: JARVIS_FONTS.mono,
          fontSize: 12,
          color: labelColor || theme.textDisabled,
        }}
      >
        {label}
      </div>
      <div style={{ color: theme.textPrimary, fontSize: 14, lineHeight: 1.6, minWidth: 0 }}>
        {children}
      </div>
      {margin ? (
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
