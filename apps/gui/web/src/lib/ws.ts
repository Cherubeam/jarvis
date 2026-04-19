// Tiny WebSocket client. Drains server events and dispatches via callback.

import type { ClientMsg, ServerEvent } from './types'

export function connect(
  url: string,
  onEvent: (ev: ServerEvent) => void,
  onClose: (reason: string) => void,
): { send: (msg: ClientMsg) => void; close: () => void } {
  const ws = new WebSocket(url)

  ws.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data) as ServerEvent
      onEvent(ev)
    } catch (err) {
      console.error('bad ws message', e.data, err)
    }
  }
  ws.onclose = () => onClose('closed')
  ws.onerror = () => onClose('error')

  return {
    send: (msg) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(msg)),
    close: () => ws.close(),
  }
}
