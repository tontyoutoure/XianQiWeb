import type { RoomDetail } from '@/stores/room'

interface RoomWsFrame {
  v?: number
  type?: unknown
  payload?: Record<string, unknown>
}

interface CreateRoomChannelOptions {
  roomId: number
  accessToken: string
  baseURL?: string
  reconnectDelayMs?: number
  onOpen?: () => void
  onClose?: () => void
  onRoomUpdate?: (room: RoomDetail) => void
}

export interface RoomChannel {
  connect: () => void
  disconnect: () => void
}

const ENV_WS_BASE_URL = (import.meta.env.VITE_WS_BASE_URL as string | undefined) ?? undefined

export function createRoomChannel(options: CreateRoomChannelOptions): RoomChannel {
  let socket: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let manuallyDisconnected = false

  const reconnectDelayMs = options.reconnectDelayMs ?? 300

  const clearReconnectTimer = () => {
    if (reconnectTimer === null) {
      return
    }
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  const scheduleReconnect = () => {
    if (manuallyDisconnected || reconnectTimer !== null) {
      return
    }
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (manuallyDisconnected) {
        return
      }
      connectSocket()
    }, reconnectDelayMs)
  }

  const connectSocket = () => {
    const url = buildRoomWsUrl(baseURLOrDefault(options.baseURL), options.roomId, options.accessToken)
    const nextSocket = new WebSocket(url)
    socket = nextSocket

    nextSocket.onopen = () => {
      options.onOpen?.()
    }

    nextSocket.onclose = () => {
      if (socket === nextSocket) {
        socket = null
      }
      options.onClose?.()
      scheduleReconnect()
    }

    nextSocket.onerror = () => {
      // Let onclose handle reconnect scheduling and state transition.
    }

    nextSocket.onmessage = (event) => {
      handleRoomMessage(event.data, nextSocket, options)
    }
  }

  const connect = () => {
    manuallyDisconnected = false
    clearReconnectTimer()
    if (socket) {
      return
    }
    connectSocket()
  }

  const disconnect = () => {
    manuallyDisconnected = true
    clearReconnectTimer()

    if (!socket) {
      return
    }

    const currentSocket = socket
    socket = null
    currentSocket.onopen = null
    currentSocket.onmessage = null
    currentSocket.onclose = null
    currentSocket.onerror = null
    currentSocket.close()
  }

  return {
    connect,
    disconnect,
  }
}

function handleRoomMessage(raw: unknown, socket: WebSocket | null, options: CreateRoomChannelOptions) {
  if (typeof raw !== 'string') {
    return
  }

  let frame: RoomWsFrame
  try {
    frame = JSON.parse(raw) as RoomWsFrame
  } catch {
    return
  }

  if (frame.type === 'PING') {
    socket?.send(JSON.stringify({ v: frame.v ?? 1, type: 'PONG', payload: {} }))
    return
  }

  if (frame.type !== 'ROOM_UPDATE') {
    return
  }

  const room = frame.payload?.room
  if (room && typeof room === 'object') {
    options.onRoomUpdate?.(room as RoomDetail)
  }
}

function baseURLOrDefault(override?: string): string {
  if (override) {
    return override
  }
  if (ENV_WS_BASE_URL) {
    return ENV_WS_BASE_URL
  }
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}`
  }
  return 'ws://127.0.0.1:18080'
}

function buildRoomWsUrl(baseURL: string, roomId: number, accessToken: string): string {
  const normalized = baseURL.replace(/\/$/, '')
  return `${normalized}/ws/rooms/${roomId}?token=${encodeURIComponent(accessToken)}`
}
