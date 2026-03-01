export type RoomStatus = 'waiting' | 'playing' | 'settlement'

export interface RoomMember {
  user_id: number
  username: string
  seat: number
  ready: boolean
  chips: number
}

export interface RoomDetail {
  room_id: number
  status: RoomStatus
  owner_id: number
  members: RoomMember[]
  current_game_id: number | null
}

export interface RoomUpdateEvent {
  type: 'ROOM_UPDATE'
  payload: {
    room: RoomDetail
  }
}

export interface RoomStoreLike {
  roomId: number | null
  roomDetail: RoomDetail | null
  loading: boolean
  error: string | null
  roomWsConnected: boolean
  coldEnded: boolean
  coldEndMessage: string | null
  lastSyncAt: number | null
  applyRoomUpdateEvent: (event: RoomUpdateEvent) => void
  toggleReady: () => void
}

type RoomStoreInitialState = Partial<Omit<RoomStoreLike, 'applyRoomUpdateEvent' | 'toggleReady'>>

let activeRoomStore: RoomStoreLike | null = null

export function createRoomStoreForTest(initialState: RoomStoreInitialState = {}): RoomStoreLike {
  const store: RoomStoreLike = {
    roomId: initialState.roomId ?? null,
    roomDetail:
      initialState.roomDetail ?? {
        room_id: initialState.roomId ?? 1,
        status: 'waiting',
        owner_id: 1,
        current_game_id: null,
        members: [{ user_id: 1, username: 'alice', seat: 0, ready: false, chips: 20 }],
      },
    loading: initialState.loading ?? false,
    error: initialState.error ?? null,
    roomWsConnected: initialState.roomWsConnected ?? false,
    coldEnded: initialState.coldEnded ?? false,
    coldEndMessage: initialState.coldEndMessage ?? null,
    lastSyncAt: initialState.lastSyncAt ?? null,
    applyRoomUpdateEvent(event: RoomUpdateEvent) {
      const prevStatus = store.roomDetail?.status
      const nextDetail = event.payload.room

      store.roomId = nextDetail.room_id
      store.roomDetail = {
        room_id: nextDetail.room_id,
        status: nextDetail.status,
        owner_id: nextDetail.owner_id,
        current_game_id: nextDetail.current_game_id,
        members: nextDetail.members.map((member) => ({ ...member })),
      }
      store.lastSyncAt = Date.now()

      if (prevStatus === 'playing' && nextDetail.status === 'waiting') {
        store.coldEnded = true
        store.coldEndMessage = '对局结束'
      }
    },
    toggleReady() {
      if (!store.roomDetail || store.roomDetail.members.length === 0) {
        return
      }

      const selfMember = store.roomDetail.members[0]
      const nextMembers = store.roomDetail.members.slice()
      nextMembers[0] = { ...selfMember, ready: !selfMember.ready }
      store.roomDetail = {
        ...store.roomDetail,
        members: nextMembers,
      }
    },
  }

  return store
}

export function setActiveRoomStore(store: RoomStoreLike) {
  activeRoomStore = store
}

export function useRoomStore(): RoomStoreLike {
  if (!activeRoomStore) {
    activeRoomStore = createRoomStoreForTest()
  }
  return activeRoomStore
}
