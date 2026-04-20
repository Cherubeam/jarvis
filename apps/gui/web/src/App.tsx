import { useCallback, useEffect, useState } from 'react'

import { LeftRail, type ViewKey } from './components/LeftRail'
import { ChatView } from './views/ChatView'
import { HistoryView } from './views/HistoryView'
import { HomeView } from './views/HomeView'
import { Stub } from './views/Stub'
import { DEFAULT_TWEAKS, type Tweaks } from './components/TweaksPanel'
import {
  ACCENT_HUES,
  JARVIS_DARK,
  JARVIS_FONTS,
  JARVIS_LIGHT,
  type Theme,
} from './lib/tokens'
import type { Agent, SessionMeta } from './lib/types'

const TWEAKS_STORAGE_KEY = 'jarvis-gui-tweaks-v1'
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
  return v && ['chat', 'home', 'agents', 'history', 'settings'].includes(v) ? v : 'chat'
}

export default function App() {
  const [tweaks, setTweaks] = useState<Tweaks>(loadTweaks)
  const [view, setView] = useState<ViewKey>(loadView)
  const [agents, setAgents] = useState<Agent[]>([])
  const [session, setSession] = useState<SessionMeta | null>(null)
  // Lifted selection for History view; Sidebar writes it, HistoryView reads.
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null)
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
  const openHistoryId = useCallback((id: string) => {
    setSelectedHistoryId(id)
    setView('history')
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
  const theme: Theme = { ...baseTheme, assistant: accent }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: theme.surface0,
        color: theme.textPrimary,
        fontFamily: tweaks.typeBias === 'mono' ? JARVIS_FONTS.mono : JARVIS_FONTS.sans,
        display: 'flex',
        overflow: 'hidden',
      }}
    >
      <LeftRail theme={theme} accent={accent} view={view} setView={setView} />
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
          onOpenHistory={openHistoryId}
          pendingSeed={pendingSeed}
          onSeedConsumed={onSeedConsumed}
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
          onStartChat={onStartChat}
        />
      )}
      {view === 'agents' && <Stub theme={theme} name="Agents" />}
      {view === 'history' && (
        <HistoryView
          theme={theme}
          accent={accent}
          refreshToken={historyRefreshToken}
          selectedId={selectedHistoryId}
          setSelectedId={setSelectedHistoryId}
          goToChat={() => setView('chat')}
        />
      )}
      {view === 'settings' && <Stub theme={theme} name="Settings" />}
    </div>
  )
}
