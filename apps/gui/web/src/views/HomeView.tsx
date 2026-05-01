// HomeView — Dashboard reachable from the left-rail's Home slot.
// Layout: 920px centered column, sections: greeting · tasks+cost row ·
// resume · recent · quick-start. Ported from JARVIS GUI.html 1475-1737.

import { useEffect, useMemo, useState } from 'react'

import { CostCard } from '../components/home/CostCard'
import { GreetingHeader } from '../components/home/GreetingHeader'
import { QuickStart } from '../components/home/QuickStart'
import { RecentCards } from '../components/home/RecentCards'
import { ResumeCard } from '../components/home/ResumeCard'
import { TasksPanel } from '../components/home/TasksPanel'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { ConversationSummary, HomeData, SessionMeta } from '../lib/types'

export function HomeView({
  theme,
  accent,
  refreshToken,
  session,
  onOpenHistory,
  onOpenHistoryRoot,
  onResume,
  onStartChat,
}: {
  theme: Theme
  accent: string
  refreshToken: number
  session: SessionMeta | null
  onOpenHistory: (id: string) => void
  onOpenHistoryRoot: () => void
  onResume: (fileId: string) => void
  onStartChat: (cmd: string | null) => void
}) {
  const [data, setData] = useState<HomeData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    const ac = new AbortController()
    fetch('/api/home', { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<HomeData>
      })
      .then((d) => {
        setData(d)
        setLoading(false)
      })
      .catch((e) => {
        if (e.name === 'AbortError') return
        setError(String(e.message || e))
        setLoading(false)
      })
    return () => ac.abort()
  }, [refreshToken])

  // Client-side active-session exclusion — server returns the absolute most
  // recent as `resume`; if that's the active chat, promote recent[0].
  const { resume, recent } = useMemo<{
    resume: ConversationSummary | null
    recent: ConversationSummary[]
  }>(() => {
    if (!data) return { resume: null, recent: [] }
    const activeId = session?.file_id
    if (activeId && data.resume?.id === activeId) {
      const [nextResume = null, ...rest] = data.recent
      return { resume: nextResume, recent: rest }
    }
    return { resume: data.resume, recent: data.recent }
  }, [data, session])

  const sectionHeader = (label: string) => (
    <div
      style={{
        fontFamily: JARVIS_FONTS.mono,
        fontSize: 10,
        letterSpacing: 1.4,
        color: theme.textDisabled,
        textTransform: 'uppercase',
        marginBottom: 10,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span>{label}</span>
      <span style={{ flex: 1, height: 1, background: theme.border }} />
    </div>
  )

  return (
    <div
      style={{
        flex: 1,
        overflow: 'auto',
        minWidth: 0,
        background: theme.surface0,
      }}
    >
      <div style={{ maxWidth: 920, margin: '0 auto', padding: '40px 48px 64px' }}>
        {loading && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.textDisabled,
            }}
          >
            loading…
          </div>
        )}
        {error && (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 12,
              color: theme.error,
              marginBottom: 20,
            }}
          >
            failed to load home: {error}
          </div>
        )}
        {data && (
          <>
            <GreetingHeader
              theme={theme}
              greeting={data.greeting}
              dayLabel={data.today.day_label}
            />

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1.6fr 1fr',
                gap: 20,
                marginBottom: 32,
              }}
            >
              <TasksPanel theme={theme} tasks={data.tasks} onOpenHistory={onOpenHistory} />
              <CostCard
                theme={theme}
                days={data.cost_week.days}
                total={data.cost_week.total}
                conversationCount={data.cost_week.conversation_count}
              />
            </div>

            <div style={{ marginBottom: 28 }}>
              {sectionHeader('Continue where you left off')}
              <ResumeCard
                theme={theme}
                accent={accent}
                resume={resume}
                onResume={() => {
                  if (resume) onResume(resume.id)
                  else onStartChat(null)
                }}
              />
            </div>

            <div style={{ marginBottom: 28 }}>
              {sectionHeader('Recent conversations')}
              <RecentCards
                theme={theme}
                accent={accent}
                items={recent}
                onOpenHistory={onOpenHistory}
                onOpenAll={onOpenHistoryRoot}
              />
            </div>

            <div>
              {sectionHeader('Quick start')}
              <QuickStart
                theme={theme}
                accent={accent}
                items={data.quick_start}
                onStartChat={onStartChat}
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
