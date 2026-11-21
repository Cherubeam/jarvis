// One category of the agent directory: a serif heading with a rule under it,
// then the entries (each AgentCard is a row of its own).

import type { ReactNode } from 'react'

import type { Theme } from '../../lib/tokens'
import { JournalRow, SectionHeading } from './journal'

export function CategorySection({
  theme,
  label,
  children,
}: {
  theme: Theme
  label: string
  children: ReactNode
  /** Kept for callers; the orchestrator's section looks like every other. */
  featured?: boolean
}) {
  return (
    <section style={{ marginTop: 14 }}>
      <JournalRow theme={theme} style={{ paddingBottom: 6 }}>
        <SectionHeading theme={theme}>{label}</SectionHeading>
      </JournalRow>
      {children}
    </section>
  )
}
