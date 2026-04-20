import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { HomeTask } from '../../lib/types'

export function TasksPanel({
  theme,
  tasks,
  onOpenHistory,
}: {
  theme: Theme
  tasks: HomeTask[]
  onOpenHistory: (id: string) => void
}) {
  const priorityDot = (p: HomeTask['priority']) => ({
    width: 6,
    height: 6,
    borderRadius: '50%',
    flexShrink: 0,
    background: p === 'high' ? theme.error : p === 'medium' ? theme.system : theme.textDisabled,
  })

  return (
    <div
      style={{
        background: theme.surface1,
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        padding: '16px 18px 14px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: theme.textPrimary }}>On your plate</div>
        <div style={{ fontFamily: JARVIS_FONTS.mono, fontSize: 10, color: theme.textDisabled }}>
          from Things 3
        </div>
      </div>
      {tasks.length === 0 ? (
        <div
          style={{
            fontFamily: JARVIS_FONTS.mono,
            fontSize: 12,
            color: theme.textDisabled,
            padding: '12px 0 4px',
          }}
        >
          no tasks · Things 3 disabled or empty lists
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {tasks.map((t, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '6px 0',
              }}
            >
              <div style={{ ...priorityDot(t.priority), marginTop: 7 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: theme.textPrimary, lineHeight: 1.4 }}>
                  {t.title}
                </div>
                <div
                  style={{
                    fontFamily: JARVIS_FONTS.mono,
                    fontSize: 10,
                    color: theme.textDisabled,
                    marginTop: 2,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    flexWrap: 'wrap',
                  }}
                >
                  {t.project && (
                    <>
                      <span>{t.project}</span>
                      <span>·</span>
                    </>
                  )}
                  <span>{t.list}</span>
                  {t.when_date && (
                    <>
                      <span>·</span>
                      <span>{t.when_date}</span>
                    </>
                  )}
                  {t.linked_conversation_ids.length > 0 && (
                    <>
                      <span>·</span>
                      <button
                        onClick={() => onOpenHistory(t.linked_conversation_ids[0])}
                        style={{
                          all: 'unset',
                          cursor: 'pointer',
                          color: theme.textSecondary,
                          textDecoration: 'underline',
                          textDecorationColor: theme.border,
                        }}
                      >
                        linked conversation →
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
