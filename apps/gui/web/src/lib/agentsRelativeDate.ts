// Humanized relative-date formatter for agent "last used" on the overview grid.
// Ported from JARVIS GUI v6 line 1742. `today` is injectable for determinism.
// Parses the isoDate with parseLocalDate to avoid the UTC-midnight weekday shift
// (same reason `dateBucket.ts` exists — see Phase 4 note).

import { parseLocalDate } from './dateBucket'

export function relativeDate(isoDate: string | null, today: Date = new Date()): string {
  if (!isoDate) return 'unused'
  const parsed = parseLocalDate(isoDate)
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const days = Math.floor((t.getTime() - parsed.getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  return `${Math.floor(days / 30)}mo ago`
}
