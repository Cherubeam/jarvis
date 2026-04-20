// ChatView — composes the design's main surface: header + stream + composer
// + status bar + palette + tweaks. Drives the WS connection.

import { useEffect, useMemo, useRef, useState } from 'react'

import { Composer } from '../components/Composer'
import { CommandPalette } from '../components/CommandPalette'
import { Sidebar } from '../components/Sidebar'
import { StatusBar } from '../components/StatusBar'
import { TweaksPanel, type Tweaks } from '../components/TweaksPanel'
import { Icon } from '../components/Icon'
import { ApprovalEvent } from '../components/events/ApprovalEvent'
import { DelegationEvent } from '../components/events/DelegationEvent'
import { RagEvent } from '../components/events/RagEvent'
import { SystemEvent } from '../components/events/SystemEvent'
import { TextEvent } from '../components/events/TextEvent'
import { ThinkingEvent } from '../components/events/ThinkingEvent'
import { ToolCallEvent } from '../components/events/ToolCallEvent'
import { UserEvent } from '../components/events/UserEvent'
import { JARVIS_FONTS, type Theme } from '../lib/tokens'
import type { Agent, ServerEvent, SessionMeta } from '../lib/types'
import { connect } from '../lib/ws'

type StreamEvent =
  | { kind: 'user'; id: string; text: string }
  | { kind: 'text'; id: string; agent: string; markdown: string; stats?: any }
  | { kind: 'tool_call'; id: string; agent: string; tool: string; args: any; result: any; elapsed_ms: number }
  | { kind: 'delegation'; id: string; from: string; to: string; reason: string }
  | { kind: 'approval'; id: string; tool: string; agent: string; path: string; diff: any[]; summary: string; resolved?: boolean; approved?: boolean }
  | { kind: 'rag'; id: string; query: string; matches: any[] }
  | { kind: 'system'; id: string; text: string; isError?: boolean }

const wsUrl = (() => {
  const { protocol, host } = window.location
  const wsProto = protocol === 'https:' ? 'wss:' : 'ws:'
  return `${wsProto}//${host}/ws/chat`
})()

export function ChatView({
  theme,
  accent,
  tweaks,
  setTweak,
  agents,
  session,
  setSession,
  historyRefreshToken,
  onTurnFinished,
  onOpenHistory,
}: {
  theme: Theme
  accent: string
  tweaks: Tweaks
  setTweak: <K extends keyof Tweaks>(k: K, v: Tweaks[K]) => void
  agents: Agent[]
  session: SessionMeta | null
  setSession: (s: SessionMeta) => void
  historyRefreshToken: number
  onTurnFinished: () => void
  onOpenHistory: (id: string) => void
}) {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [thinking, setThinking] = useState<string | null>(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [totals, setTotals] = useState({ messages: 0, tokens: 0, cost: 0 })
  const [inFlight, setInFlight] = useState(false)
  const [composerSeed, setComposerSeed] = useState('')
  const wsRef = useRef<ReturnType<typeof connect> | null>(null)
  const streamRef = useRef<HTMLDivElement | null>(null)

  // Connect WS
  useEffect(() => {
    const conn = connect(
      wsUrl,
      (ev) => handleServerEvent(ev),
      (reason) => {
        console.warn('ws closed:', reason)
        setEvents((prev) => [
          ...prev,
          { kind: 'system', id: 's-' + Date.now(), text: `connection ${reason}`, isError: true },
        ])
      },
    )
    wsRef.current = conn
    return () => conn.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-scroll
  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight })
  }, [events, thinking])

  // ⌘K palette
  useEffect(() => {
    const kd = (ev: KeyboardEvent) => {
      if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === 'k') {
        ev.preventDefault()
        setPaletteOpen(true)
      } else if (ev.key === 'Escape') {
        setPaletteOpen(false)
      }
    }
    window.addEventListener('keydown', kd)
    return () => window.removeEventListener('keydown', kd)
  }, [])

  function handleServerEvent(ev: ServerEvent) {
    if (ev.type === 'session_start') {
      setSession(ev.session)
      return
    }
    if (ev.type === 'system') {
      setEvents((prev) => [...prev, { kind: 'system', id: 's-' + Date.now(), text: ev.text }])
      return
    }
    if (ev.type === 'user') {
      setEvents((prev) => [...prev, { kind: 'user', id: ev.id, text: ev.text }])
      return
    }
    if (ev.type === 'thinking_start') {
      setThinking(ev.agent)
      return
    }
    if (ev.type === 'thinking_end') {
      setThinking(null)
      return
    }
    if (ev.type === 'chunk') {
      // Buffer until 'text' arrives. Simplest: render as a streaming text row.
      setEvents((prev) => {
        const last = prev[prev.length - 1]
        if (last && last.kind === 'text' && last.id === ev.id) {
          return [...prev.slice(0, -1), { ...last, markdown: last.markdown + ev.delta }]
        }
        return [
          ...prev,
          {
            kind: 'text',
            id: ev.id,
            agent: ev.agent,
            markdown: ev.delta,
          },
        ]
      })
      return
    }
    if (ev.type === 'text') {
      setEvents((prev) => {
        const idx = prev.findIndex((e) => e.kind === 'text' && e.id === ev.id)
        if (idx >= 0) {
          const next = prev.slice()
          next[idx] = { kind: 'text', id: ev.id, agent: ev.agent, markdown: ev.markdown, stats: ev.stats }
          return next
        }
        return [
          ...prev,
          { kind: 'text', id: ev.id, agent: ev.agent, markdown: ev.markdown, stats: ev.stats },
        ]
      })
      return
    }
    if (ev.type === 'tool_call') {
      setEvents((prev) => [
        ...prev,
        {
          kind: 'tool_call',
          id: ev.id,
          agent: ev.agent,
          tool: ev.tool,
          args: ev.args,
          result: ev.result,
          elapsed_ms: ev.elapsed_ms,
        },
      ])
      return
    }
    if (ev.type === 'delegation') {
      setEvents((prev) => [
        ...prev,
        { kind: 'delegation', id: ev.id, from: ev.from, to: ev.to, reason: ev.reason },
      ])
      return
    }
    if (ev.type === 'approval_pending') {
      setEvents((prev) => [
        ...prev,
        {
          kind: 'approval',
          id: ev.id,
          tool: ev.tool,
          agent: ev.agent,
          path: ev.path,
          diff: ev.diff,
          summary: ev.summary,
        },
      ])
      return
    }
    if (ev.type === 'approval_resolved') {
      setEvents((prev) =>
        prev.map((e) =>
          e.kind === 'approval' && e.id === ev.id ? { ...e, resolved: true, approved: ev.approved } : e,
        ),
      )
      return
    }
    if (ev.type === 'rag_result') {
      setEvents((prev) => [
        ...prev,
        { kind: 'rag', id: ev.id, query: ev.query, matches: ev.matches },
      ])
      return
    }
    if (ev.type === 'error') {
      setEvents((prev) => [
        ...prev,
        { kind: 'system', id: 'err-' + Date.now(), text: ev.message, isError: true },
      ])
      return
    }
    if (ev.type === 'totals') {
      setTotals({ messages: ev.messages, tokens: ev.tokens, cost: ev.cost })
      return
    }
    if (ev.type === 'turn_finished') {
      setInFlight(false)
      onTurnFinished()
      return
    }
  }

  function submit(text: string) {
    if (inFlight) return
    setInFlight(true)
    wsRef.current?.send({ type: 'submit', text })
  }

  function pickCommand(a: Agent) {
    setPaletteOpen(false)
    if (a.command) setComposerSeed(a.command + ' ')
  }

  function approve(id: string) {
    wsRef.current?.send({ type: 'approval_decision', id, approved: true })
  }
  function reject(id: string) {
    wsRef.current?.send({ type: 'approval_decision', id, approved: false })
  }

  const headerAgent = useMemo(() => session?.id || 'Personal Assistant', [session])

  return (
    <main
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: 'relative',
        background: theme.surface0,
      }}
    >
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        <Sidebar
          theme={theme}
          accent={accent}
          visible={tweaks.sidebar}
          session={session}
          refreshToken={historyRefreshToken}
          onOpen={onOpenHistory}
        />

        <main
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          {/* Session header */}
          <div
            style={{
              padding: '14px 28px 10px',
              borderBottom: `1px solid ${theme.border}`,
              display: 'flex',
              alignItems: 'center',
              gap: 14,
            }}
          >
            <div>
              <div
                style={{
                  fontFamily: JARVIS_FONTS.sans,
                  fontSize: 15,
                  fontWeight: 600,
                  color: theme.textPrimary,
                  letterSpacing: -0.1,
                }}
              >
                Personal Assistant
              </div>
              <div
                style={{
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                  color: theme.textDisabled,
                  marginTop: 2,
                }}
              >
                {session?.conversation_path || '…'}
              </div>
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              <button
                onClick={() => setEditMode((m) => !m)}
                title="Tweaks"
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: `1px solid ${theme.border}`,
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                  color: theme.textSecondary,
                }}
              >
                tweaks
              </button>
              <button
                onClick={() => setPaletteOpen(true)}
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: `1px solid ${theme.border}`,
                  fontFamily: JARVIS_FONTS.mono,
                  fontSize: 11,
                  color: theme.textSecondary,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <Icon name="slash" size={11} color={accent} />
                commands
                <span style={{ color: theme.textDisabled, marginLeft: 4 }}>⌘K</span>
              </button>
            </div>
          </div>

          {/* Stream */}
          <div
            ref={streamRef}
            style={{ flex: 1, overflowY: 'auto', paddingTop: 8, paddingBottom: 24 }}
          >
            {events.map((e) => {
              const dense = tweaks.density === 'compact'
              switch (e.kind) {
                case 'user':
                  return <UserEvent key={e.id} e={{ text: e.text }} theme={theme} dense={dense} />
                case 'text':
                  return (
                    <TextEvent
                      key={e.id}
                      e={{ agent: e.agent, markdown: e.markdown, stats: e.stats }}
                      theme={theme}
                      dense={dense}
                      showStats={tweaks.showStats}
                    />
                  )
                case 'tool_call':
                  return (
                    <ToolCallEvent
                      key={e.id}
                      e={{
                        id: e.id,
                        agent: e.agent,
                        tool: e.tool,
                        args: e.args,
                        result: e.result,
                        elapsed_ms: e.elapsed_ms,
                      }}
                      theme={theme}
                      dense={dense}
                      style={tweaks.toolStyle}
                    />
                  )
                case 'delegation':
                  return (
                    <DelegationEvent
                      key={e.id}
                      e={{ from: e.from, to: e.to, reason: e.reason }}
                      theme={theme}
                      dense={dense}
                    />
                  )
                case 'approval':
                  return e.resolved ? (
                    <SystemEvent
                      key={e.id}
                      e={{ text: e.approved ? `Approved · wrote ${e.path}` : 'Rejected. Nothing written to vault.' }}
                      theme={theme}
                      dense={dense}
                    />
                  ) : (
                    <ApprovalEvent
                      key={e.id}
                      e={{
                        id: e.id,
                        tool: e.tool,
                        agent: e.agent,
                        path: e.path,
                        diff: e.diff,
                        summary: e.summary,
                      }}
                      theme={theme}
                      onApprove={() => approve(e.id)}
                      onReject={() => reject(e.id)}
                      dense={dense}
                    />
                  )
                case 'rag':
                  return (
                    <RagEvent
                      key={e.id}
                      e={{ query: e.query, matches: e.matches }}
                      theme={theme}
                      dense={dense}
                    />
                  )
                case 'system':
                  return (
                    <SystemEvent
                      key={e.id}
                      e={{ text: e.text }}
                      theme={theme}
                      dense={dense}
                      isError={e.isError}
                    />
                  )
              }
            })}
            {thinking && <ThinkingEvent theme={theme} agent={thinking} />}
          </div>

          <ComposerWrapper
            seed={composerSeed}
            onConsumed={() => setComposerSeed('')}
            theme={theme}
            accent={accent}
            disabled={inFlight}
            onSubmit={submit}
            onOpenPalette={() => setPaletteOpen(true)}
          />

          <CommandPalette
            theme={theme}
            open={paletteOpen}
            onClose={() => setPaletteOpen(false)}
            onPick={pickCommand}
            agents={agents}
          />

          <TweaksPanel
            theme={theme}
            open={editMode}
            tweaks={tweaks}
            setTweak={setTweak}
            onClose={() => setEditMode(false)}
          />
        </main>
      </div>

      <StatusBar
        theme={theme}
        agent="JARVIS"
        totals={totals}
        showStats={tweaks.showStats}
        session={session}
      />
    </main>
  )
}

// Composer wrapper that lets palette pick prefill the input.
function ComposerWrapper({
  seed,
  onConsumed,
  ...props
}: {
  seed: string
  onConsumed: () => void
  theme: Theme
  accent: string
  disabled?: boolean
  onSubmit: (t: string) => void
  onOpenPalette: () => void
}) {
  // Seed is consumed by submitting it directly (the palette picks a slash command).
  useEffect(() => {
    if (seed) {
      props.onSubmit(seed)
      onConsumed()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed])
  return <Composer {...props} />
}
