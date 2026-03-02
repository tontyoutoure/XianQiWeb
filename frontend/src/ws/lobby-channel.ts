import type { RoomSummary } from '@/stores/lobby'

interface LobbyWsFrame {
  v?: number
  type?: unknown
  payload?: Record<string, unknown>
}

interface CreateLobbyChannelOptions {
  accessToken: string
  baseURL?: string
  onOpen?: () => void
  onClose?: () => void
  onRoomList?: (rooms: RoomSummary[]) => void
  onRoomUpdate?: (room: RoomSummary) => void
}

export interface LobbyChannel {
  connect: () => void
  disconnect: () => void
}

const ENV_WS_BASE_URL = (import.meta.env.VITE_WS_BASE_URL as string | undefined) ?? undefined

export function createLobbyChannel(options: CreateLobbyChannelOptions): LobbyChannel {
  let socket: WebSocket | null = null

  const connect = () => {
    const url = buildLobbyWsUrl(baseURLOrDefault(options.baseURL), options.accessToken)
    socket = new WebSocket(url)

    socket.onopen = () => {
      options.onOpen?.()
    }

    socket.onclose = () => {
      options.onClose?.()
    }

    socket.onerror = () => {
      options.onClose?.()
    }

    socket.onmessage = (event) => {
      handleLobbyMessage(event.data, socket, options)
    }
  }

  const disconnect = () => {
    if (!socket) {
      return
    }
    socket.onopen = null
    socket.onmessage = null
    socket.onclose = null
    socket.onerror = null
    socket.close()
    socket = null
  }

  return {
    connect,
    disconnect,
  }
}

function handleLobbyMessage(raw: unknown, socket: WebSocket | null, options: CreateLobbyChannelOptions) {
  if (typeof raw !== 'string') {
    return
  }

  let frame: LobbyWsFrame
  try {
    frame = JSON.parse(raw) as LobbyWsFrame
  } catch {
    return
  }

  if (frame.type === 'PING') {
    socket?.send(JSON.stringify({ v: frame.v ?? 1, type: 'PONG', payload: {} }))
    return
  }

  if (frame.type === 'ROOM_LIST') {
    const rooms = frame.payload?.rooms
    if (Array.isArray(rooms)) {
      options.onRoomList?.(rooms as RoomSummary[])
    }
    return
  }

  if (frame.type === 'ROOM_UPDATE') {
    const room = frame.payload?.room
    if (room && typeof room === 'object') {
      options.onRoomUpdate?.(room as RoomSummary)
    }
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

function buildLobbyWsUrl(baseURL: string, accessToken: string): string {
  const normalized = baseURL.replace(/\/$/, '')
  return `${normalized}/ws/lobby?token=${encodeURIComponent(accessToken)}`
}
