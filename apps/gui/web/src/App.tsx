import { useCallback, useEffect, useState } from 'react'

import { TopNav, type ViewKey } from './components/TopNav'
import { AgentDetailView } from './views/AgentDetailView'
import { AgentsView } from './views/AgentsView'
import { ChatView } from './views/ChatView'
import { HistoryView } from './views/HistoryView'
import { HomeView } from './views/HomeView'
import { OutcomesView } from './views/OutcomesView'
import { SettingsView } from './views/SettingsView'
import { DEFAULT_TWEAKS, type Tweaks } from './components/TweaksPanel'
import {
  ACCENT_HUES,
  JARVIS_DARK,
  JARVIS_FONTS,
  JARVIS_LIGHT,
  type Theme,
} from './lib/tokens'
import type { Agent, SessionMeta } from './lib/types'

// v2: the Journal look replaced the accent keys and the type switch, so v1
// values no longer fit; stored v1 tweaks are ignored, not migrated.
const TWEAKS_STORAGE_KEY = 'jarvis-gui-tweaks-v2'
const VIEW_STORAGE_KEY = 'jarvis-gui-view-v1'

function loadTweaks(): Tweaks {
  try {
    const raw = localStorage.getItem(TWEAKS_STORAGE_KEY)
    if (!raw) return DEFAULT_TWEAKS
    return { ...DEFAULT_TWEAKS, ...(JSON.parse(raw) as Partial<Tweaks>) }
  } catch {
    return DEFAULT_TWEAKS
  }
}

function loadView(): ViewKey {
  const v = localStorage.getItem(VIEW_STORAGE_KEY) as ViewKey | null
  // 'agent' (detail) is NOT persisted — a refresh on the detail page lands on
  // 'agents' (the overview grid) because `selectedAgentId` doesn't survive reloads.
  return v && ['chat', 'home', 'agents', 'outcomes', 'history', 'settings'].includes(v) ? v : 'chat'
}

export default function App() {
  const [tweaks, setTweaks] = useState<Tweaks>(loadTweaks)
  const [view, setView] = useState<ViewKey>(loadView)
  const [agents, setAgents] = useState<Agent[]>([])
  const [session, setSession] = useState<SessionMeta | null>(null)
  // Lifted selection for History view; Sidebar writes it, HistoryView reads.
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null)
  // Agents detail sub-view target. Cleared when the user leaves detail.
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  // Bumped when a turn finishes so Sidebar + HistoryView + HomeView invalidate and re-fetch.
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0)
  const bumpHistoryRefresh = useCallback(
    () => setHistoryRefreshToken((n) => n + 1),
    [],
  )
  // Pending composer seed — set by Home's Quick Start; ChatView submits it
  // once the WS is open (guards against the race where ChatView mounts and
  // tries to send before session_start arrives).
  const [pendingSeed, setPendingSeed] = useState<string | null>(null)
  const onSeedConsumed = useCallback(() => setPendingSeed(null), [])
  const onStartChat = useCallback((cmd: string | null) => {
    setPendingSeed(cmd)
    setView('chat')
  }, [])
  // Pending resume target — set by the History detail-pane resume button.
  // ChatView consumes it once the WS is open and emits the `resume` message,
  // mirroring the pendingSeed pattern. `null` = no pending resume.
  const [pendingResumeId, setPendingResumeId] = useState<string | null>(null)
  const onResumeConsumed = useCallback(() => setPendingResumeId(null), [])
  const onResumeFromHistory = useCallback((fileId: string) => {
    setPendingResumeId(fileId)
    setView('chat')
  }, [])
  const openHistoryId = useCallback((id: string) => {
    setSelectedHistoryId(id)
    setView('history')
  }, [])
  const openAgent = useCallback((id: string) => {
    setSelectedAgentId(id)
    setView('agent')
  }, [])
  // Clicking the Agents nav link while on detail should return to the grid.
  const setViewWithAgentReset = useCallback((v: ViewKey) => {
    if (v === 'agents') setSelectedAgentId(null)
    setView(v)
  }, [])

  useEffect(() => {
    localStorage.setItem(TWEAKS_STORAGE_KEY, JSON.stringify(tweaks))
  }, [tweaks])

  useEffect(() => {
    localStorage.setItem(VIEW_STORAGE_KEY, view)
  }, [view])

  useEffect(() => {
    fetch('/api/agents')
      .then((r) => r.json())
      .then((data: Agent[]) => setAgents(data))
      .catch((err) => console.error('failed to load agents', err))
  }, [])

  function setTweak<K extends keyof Tweaks>(k: K, v: Tweaks[K]) {
    setTweaks((prev) => ({ ...prev, [k]: v }))
  }

  const baseTheme: Theme = tweaks.mode === 'light' ? JARVIS_LIGHT : JARVIS_DARK
  const accent = ACCENT_HUES[tweaks.accent][tweaks.mode === 'light' ? 'light' : 'dark']
  const theme: Theme = {
    ...baseTheme,
    assistant: accent,
    read: tweaks.reading === 'mono' ? JARVIS_FONTS.mono : JARVIS_FONTS.serif,
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: theme.surface0,
        color: theme.textPrimary,
        fontFamily: JARVIS_FONTS.mono,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <TopNav
        theme={theme}
        view={view === 'agent' ? 'agents' : view}
        setView={setViewWithAgentReset}
      />
      <div style={{ flex: 1, minHeight: 0, display: 'flex', overflow: 'hidden' }}>
      {view === 'chat' && (
        <ChatView
          theme={theme}
          accent={accent}
          tweaks={tweaks}
          setTweak={setTweak}
          agents={agents}
          session={session}
          setSession={setSession}
          historyRefreshToken={historyRefreshToken}
          onTurnFinished={bumpHistoryRefresh}
          pendingSeed={pendingSeed}
          onSeedConsumed={onSeedConsumed}
          pendingResumeId={pendingResumeId}
          onResumeConsumed={onResumeConsumed}
        />
      )}
      {view === 'home' && (
        <HomeView
          theme={theme}
          accent={accent}
          refreshToken={historyRefreshToken}
          session={session}
          onOpenHistory={openHistoryId}
          onOpenHistoryRoot={() => setView('history')}
          onResume={onResumeFromHistory}
          onStartChat={onStartChat}
        />
      )}
      {view === 'agents' && (
        <AgentsView
          theme={theme}
          accent={accent}
          agents={agents}
          refreshToken={historyRefreshToken}
          onOpenAgent={openAgent}
        />
      )}
      {view === 'agent' && selectedAgentId && (
        <AgentDetailView
          theme={theme}
          accent={accent}
          agentId={selectedAgentId}
          refreshToken={historyRefreshToken}
          onBack={() => {
            setSelectedAgentId(null)
            setView('agents')
          }}
          onStartSession={(cmd) => {
            setSelectedAgentId(null)
            onStartChat(cmd ? cmd + ' ' : null)
          }}
        />
      )}
      {view === 'outcomes' && (
        <OutcomesView
          theme={theme}
          accent={accent}
          refreshToken={historyRefreshToken}
        />
      )}
      {view === 'history' && (
        <HistoryView
          theme={theme}
          accent={accent}
          refreshToken={historyRefreshToken}
          selectedId={selectedHistoryId}
          setSelectedId={setSelectedHistoryId}
          onResume={onResumeFromHistory}
          onConversationDeleted={bumpHistoryRefresh}
        />
      )}
      {view === 'settings' && <SettingsView theme={theme} accent={accent} />}
      </div>
    </div>
  )
}
