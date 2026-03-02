import { reactive } from 'vue'

export type RoomStatus = 'waiting' | 'playing' | 'settlement'

export interface RoomSummary {
  room_id: number
  status: RoomStatus
  player_count: number
  ready_count: number
}

export interface LobbyRoomListEvent {
  type: 'ROOM_LIST'
  payload: {
    rooms: RoomSummary[]
  }
}

export interface LobbyRoomUpdateEvent {
  type: 'ROOM_UPDATE'
  payload: {
    room: RoomSummary
  }
}

export type LobbyWsEvent = LobbyRoomListEvent | LobbyRoomUpdateEvent

export interface LobbyStoreLike {
  rooms: RoomSummary[]
  loading: boolean
  error: string | null
  lobbyWsConnected: boolean
  lastSyncAt: number | null
  applyRoomListEvent: (event: LobbyWsEvent) => void
}

type LobbyStoreInitialState = Partial<Omit<LobbyStoreLike, 'applyRoomListEvent'>>

let activeLobbyStore: LobbyStoreLike | null = null

export function createLobbyStoreForTest(initialState: LobbyStoreInitialState = {}): LobbyStoreLike {
  let proxyStore: LobbyStoreLike | null = null
  const store: LobbyStoreLike = {
    rooms:
      initialState.rooms?.map((room) => ({ ...room })) ?? [
        { room_id: 1, status: 'waiting', player_count: 0, ready_count: 0 },
      ],
    loading: initialState.loading ?? false,
    error: initialState.error ?? null,
    lobbyWsConnected: initialState.lobbyWsConnected ?? false,
    lastSyncAt: initialState.lastSyncAt ?? null,
    applyRoomListEvent(event: LobbyWsEvent) {
      const target = proxyStore ?? store
      if (event.type === 'ROOM_LIST') {
        target.rooms = event.payload.rooms.map((room) => ({ ...room })).sort(compareRoomsForLobby)
        target.lastSyncAt = Date.now()
        return
      }

      const updateRoom = event.payload.room
      const targetIndex = target.rooms.findIndex((room) => room.room_id === updateRoom.room_id)
      if (targetIndex === -1) {
        target.rooms = [...target.rooms, { ...updateRoom }].sort(compareRoomsForLobby)
      } else {
        const nextRooms = target.rooms.slice()
        nextRooms[targetIndex] = { ...updateRoom }
        target.rooms = nextRooms.sort(compareRoomsForLobby)
      }
      target.lastSyncAt = Date.now()
    },
  }

  proxyStore = reactive(store) as LobbyStoreLike
  return proxyStore
}

function compareRoomsForLobby(left: RoomSummary, right: RoomSummary): number {
  if (left.player_count !== right.player_count) {
    return left.player_count - right.player_count
  }
  return left.room_id - right.room_id
}

export function setActiveLobbyStore(store: LobbyStoreLike) {
  activeLobbyStore = store
}

export function useLobbyStore(): LobbyStoreLike {
  if (!activeLobbyStore) {
    activeLobbyStore = createLobbyStoreForTest()
  }
  return activeLobbyStore
}
