import { JARVIS_FONTS, type Theme } from '../../lib/tokens'
import type { HomeTask } from '../../lib/types'
import { Row } from '../events/Row'

/** Today's tasks as a plain list under a heading; where they come from is a
 *  margin note. The rule above sets the lists off from the briefing. */
export function TasksPanel({
  theme,
  tasks,
  onOpenHistory,
}: {
  theme: Theme
  tasks: HomeTask[]
  onOpenHistory: (id: string) => void
}) {
  // Priority is told by shape, not hue: filled for high, a ring for medium,
  // a faint ring for low.
  const priorityDot = (p: HomeTask['priority']) => ({
    width: 7,
    height: 7,
    borderRadius: '50%',
    flexShrink: 0,
    boxSizing: 'border-box' as const,
    background: p === 'high' ? theme.textPrimary : 'transparent',
    border: `1.5px solid ${
      p === 'high' ? theme.textPrimary : p === 'medium' ? theme.textSecondary : theme.borderStrong
    }`,
  })
  const serif = theme.read === JARVIS_FONTS.serif

  return (
    <Row theme={theme} label="" margin="from Things 3">
      <div style={{ borderTop: `1px solid ${theme.border}`, marginTop: 12, paddingTop: 22 }}>
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
          On your plate
        </h2>
        {tasks.length === 0 ? (
          <div
            style={{
              fontFamily: JARVIS_FONTS.mono,
              fontSize: 13,
              color: theme.textDisabled,
            }}
          >
            no tasks · Things 3 disabled or empty lists
          </div>
        ) : (
          <ul
            style={{
              listStyle: 'none',
              margin: 0,
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            {tasks.map((t, i) => (
              <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <span
                  role="img"
                  aria-label={`${t.priority} priority`}
                  style={{ ...priorityDot(t.priority), marginTop: serif ? 10 : 8 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontFamily: theme.read,
                      fontSize: serif ? 17 : 14,
                      color: theme.textPrimary,
                      lineHeight: 1.5,
                    }}
                  >
                    {t.title}
                  </div>
                  <div
                    style={{
                      fontFamily: JARVIS_FONTS.mono,
                      fontSize: 12,
                      lineHeight: 1.5,
                      color: theme.textDisabled,
                      display: 'flex',
                      alignItems: 'baseline',
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
                            background: 'none',
                            border: 0,
                            padding: 0,
                            margin: 0,
                            cursor: 'pointer',
                            fontFamily: JARVIS_FONTS.mono,
                            fontSize: 12,
                            lineHeight: 1.5,
                            color: theme.assistant,
                            textDecoration: 'underline',
                            textUnderlineOffset: 3,
                          }}
                        >
                          linked conversation →
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Row>
  )
}
