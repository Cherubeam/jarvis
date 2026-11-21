// HomeView — the page behind the Home link, laid out as a journal page:
// greeting (weekly cost in the margin) · morning briefing · tasks · resume ·
// recent · quick-start. Each section is one row of the journal grid
// (`.jr-row` in index.html): gutter, reading column, margin note.

import { useEffect, useMemo, useState } from 'react'

import { Row } from '../components/events/Row'
import { BriefingCard } from '../components/home/BriefingCard'
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
    <h2
      style={{
        margin: '0 0 10px',
        fontFamily: JARVIS_FONTS.serif,
        fontSize: 18,
        fontWeight: 600,
        lineHeight: 1.3,
        color: theme.textPrimary,
      }}
    >
      {label}
    </h2>
  )

  // Whitespace, not a box, sets one section off from the next.
  const sectionGap = { paddingTop: 16 }

  return (
    <div
      className="jr-pane"
      style={{
        flex: 1,
        overflow: 'auto',
        minWidth: 0,
        background: theme.surface0,
      }}
    >
      <div style={{ paddingTop: 26, paddingBottom: 64 }}>
        {loading && (
          <Row theme={theme} label="">
            <div
              style={{
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 13,
                color: theme.textDisabled,
              }}
            >
              loading…
            </div>
          </Row>
        )}
        {error && (
          <Row theme={theme} label="">
            <div
              style={{
                fontFamily: JARVIS_FONTS.mono,
                fontSize: 13,
                color: theme.error,
              }}
            >
              failed to load home: {error}
            </div>
          </Row>
        )}
        {data && (
          <>
            <Row
              theme={theme}
              label=""
              margin={
                <CostCard
                  theme={theme}
                  days={data.cost_week.days}
                  total={data.cost_week.total}
                  conversationCount={data.cost_week.conversation_count}
                />
              }
            >
              <GreetingHeader
                theme={theme}
                greeting={data.greeting}
                dayLabel={data.today.day_label}
              />
            </Row>

            <BriefingCard theme={theme} briefing={data.briefing} today={data.today.date} />

            <TasksPanel theme={theme} tasks={data.tasks} onOpenHistory={onOpenHistory} />

            <Row theme={theme} label="">
              <div style={sectionGap}>
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
            </Row>

            <Row theme={theme} label="">
              <div style={sectionGap}>
                {sectionHeader('Recent conversations')}
                <RecentCards
                  theme={theme}
                  accent={accent}
                  items={recent}
                  onOpenHistory={onOpenHistory}
                  onOpenAll={onOpenHistoryRoot}
                />
              </div>
            </Row>

            <Row theme={theme} label="">
              <div style={sectionGap}>
                {sectionHeader('Quick start')}
                <QuickStart
                  theme={theme}
                  accent={accent}
                  items={data.quick_start}
                  onStartChat={onStartChat}
                />
              </div>
            </Row>
          </>
        )}
      </div>
    </div>
  )
}
