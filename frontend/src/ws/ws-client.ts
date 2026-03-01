interface WsFrame {
  v: number
  type: string
  payload: Record<string, unknown>
}

interface TestSocketLike {
  send: (raw: string) => void
}

export interface WsClientForTest {
  bindSocket: (socket: TestSocketLike) => void
  onRawMessage: (raw: string) => void
  isConnectionAlive: () => boolean
}

export function createWsClientForTest(): WsClientForTest {
  let socket: TestSocketLike | null = null
  let alive = false

  return {
    bindSocket(nextSocket) {
      socket = nextSocket
      alive = true
    },
    onRawMessage(raw) {
      let frame: WsFrame
      try {
        frame = JSON.parse(raw) as WsFrame
      } catch {
        return
      }

      if (frame.type === 'PING') {
        socket?.send(
          JSON.stringify({
            v: frame.v ?? 1,
            type: 'PONG',
            payload: {},
          }),
        )
        alive = true
        return
      }

      if (frame.type === 'PONG') {
        alive = true
      }
    },
    isConnectionAlive() {
      return alive
    },
  }
}
