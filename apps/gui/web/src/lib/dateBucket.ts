// Groups a conversation date into one of the prototype's sticky buckets.
// Ported from JARVIS GUI.html line 836.

export type DateBucket = 'Today' | 'Yesterday' | 'This week' | 'Last week' | 'Earlier'

export const BUCKET_ORDER: DateBucket[] = [
  'Today', 'Yesterday', 'This week', 'Last week', 'Earlier',
]

export function dateBucket(dateStr: string, today: Date = new Date()): DateBucket {
  // Normalize today to midnight so same-day entries bucket correctly regardless of time.
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const d = new Date(dateStr)
  const days = Math.floor((t.getTime() - d.getTime()) / 86_400_000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days <= 6) return 'This week'
  if (days <= 13) return 'Last week'
  return 'Earlier'
}
