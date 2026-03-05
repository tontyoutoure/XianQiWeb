<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import IngameShell from '@/components/ingame/IngameShell.vue'
import { createGamesApi, isGamesApiError } from '@/services/games-api'
import { createRoomsApi, isRoomsApiError } from '@/services/rooms-api'
import { useAuthStore } from '@/stores/auth'
import { useLobbyStore } from '@/stores/lobby'
import { useRoomStore, type RoomDetail } from '@/stores/room'
import {
  createRoomChannel,
  type RoomGamePrivatePayload,
  type RoomGamePublicPayload,
} from '@/ws/room-channel'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const lobbyStore = useLobbyStore()
const roomStore = useRoomStore()
const roomsApi = createRoomsApi()
const gamesApi = createGamesApi()
const FORCE_SERVICE_RESET_KEY = 'xianqi.force_service_reset'
const SERVICE_RESET_NOTICE_KEY = 'xianqi.lobby_service_reset_notice'
const SERVICE_RESET_MESSAGE = '服务已重置，请重新入房'
const ACTION_TYPES = ['BUCKLE', 'PASS_BUCKLE', 'REVEAL', 'PASS_REVEAL', 'PLAY', 'COVER'] as const
let cleanupRoomChannel: (() => void) | null = null
const gamePublicState = ref<Record<string, unknown> | null>(null)
const gamePrivateState = ref<Record<string, unknown> | null>(null)
const gameLegalActions = ref<Record<string, unknown> | null>(null)
const gameLatestEvent = ref<Record<string, unknown> | null>(null)
const gameSettlement = ref<Record<string, unknown> | null>(null)
const actionSubmitting = ref(false)

interface LegalActionLike {
  type?: unknown
}

interface LegalActionsLike {
  actions?: unknown
}

const readyCountText = computed(() => {
  const members = roomStore.roomDetail?.members ?? []
  const readyCount = members.filter((member) => member.ready).length
  return `ready ${readyCount}/${members.length}`
})

const actionDisabledMap = computed<Record<string, boolean> | null>(() => {
  if (!actionSubmitting.value) {
    return null
  }

  const disabledMap: Record<string, boolean> = {}
  for (const actionType of ACTION_TYPES) {
    disabledMap[actionType] = true
  }
  return disabledMap
})

const resolvedGamePhase = computed<string | undefined>(() => {
  const phase = gamePublicState.value?.phase
  if (typeof phase === 'string' && phase.trim().length > 0) {
    return phase
  }
  return undefined
})

onMounted(() => {
  const shouldForceReset =
    typeof window !== 'undefined' && window.sessionStorage.getItem(FORCE_SERVICE_RESET_KEY) === '1'
  if (!shouldForceReset) {
    const currentRoomId = resolveCurrentRoomId()
    if (currentRoomId !== null) {
      roomStore.roomId = currentRoomId
    }

    void hydrateRoomDetail()
    return
  }

  window.sessionStorage.removeItem(FORCE_SERVICE_RESET_KEY)
  window.sessionStorage.setItem(SERVICE_RESET_NOTICE_KEY, '1')
  lobbyStore.error = SERVICE_RESET_MESSAGE
  void router.replace('/lobby')
})

onUnmounted(() => {
  cleanupRoomChannel?.()
  cleanupRoomChannel = null
})

async function onToggleReady() {
  const roomId = resolveCurrentRoomId()
  if (!authStore.accessToken || roomId === null) {
    roomStore.error = '未登录或房间信息无效'
    return
  }

  const selfId = authStore.user?.id
  if (!selfId) {
    roomStore.error = '未登录或会话已失效'
    return
  }

  roomStore.loading = true
  roomStore.error = null
  try {
    const latestDetail = await roomsApi.getRoomDetail(authStore.accessToken, roomId)
    const latestSelfMember = latestDetail.members.find((member) => member.user_id === selfId)
    if (!latestSelfMember) {
      roomStore.error = '当前用户不在房间中'
      return
    }

    const detail = await roomsApi.setReady(authStore.accessToken, roomId, !latestSelfMember.ready)
    roomStore.applyRoomUpdateEvent({
      type: 'ROOM_UPDATE',
      payload: {
        room: detail,
      },
    })
    await syncGameStateFromRoomDetail(detail)
  } catch (error) {
    if (isServiceResetBoundaryError(error)) {
      triggerServiceResetBoundary()
      return
    }
    roomStore.error = resolveErrorMessage(error)
  } finally {
    roomStore.loading = false
  }
}

async function onLeave() {
  const roomId = resolveCurrentRoomId()
  if (!authStore.accessToken || roomId === null) {
    roomStore.error = '未登录或房间信息无效'
    return
  }

  roomStore.loading = true
  roomStore.error = null
  try {
    await roomsApi.leaveRoom(authStore.accessToken, roomId)
    cleanupRoomChannel?.()
    cleanupRoomChannel = null
    roomStore.roomWsConnected = false
    resetGameSnapshots()
    await router.push('/lobby')
  } catch (error) {
    roomStore.error = resolveErrorMessage(error)
  } finally {
    roomStore.loading = false
  }
}

async function hydrateRoomDetail() {
  const roomId = resolveCurrentRoomId()
  if (!authStore.accessToken || roomId === null) {
    roomStore.error = '未登录或房间信息无效'
    return
  }

  roomStore.loading = true
  roomStore.error = null
  try {
    const detail = await roomsApi.getRoomDetail(authStore.accessToken, roomId)
    if (!isCurrentUserInRoom(detail)) {
      triggerServiceResetBoundary()
      return
    }
    roomStore.applyRoomUpdateEvent({
      type: 'ROOM_UPDATE',
      payload: {
        room: detail,
      },
    })
    connectRoomChannel(roomId, authStore.accessToken)
    await syncGameStateFromRoomDetail(detail)
  } catch (error) {
    if (isServiceResetBoundaryError(error)) {
      triggerServiceResetBoundary()
      return
    }
    roomStore.error = resolveErrorMessage(error)
  } finally {
    roomStore.loading = false
  }
}

function connectRoomChannel(roomId: number, accessToken: string) {
  cleanupRoomChannel?.()
  cleanupRoomChannel = null

  const channel = createRoomChannel({
    roomId,
    accessToken,
    onOpen: () => {
      roomStore.roomWsConnected = true
      void resyncRoomDetail(roomId)
    },
    onClose: () => {
      roomStore.roomWsConnected = false
    },
    onRoomUpdate: (room) => {
      if (!isCurrentUserInRoom(room)) {
        triggerServiceResetBoundary()
        return
      }
      roomStore.applyRoomUpdateEvent({
        type: 'ROOM_UPDATE',
        payload: { room },
      })
      void syncGameStateFromRoomDetail(room)
    },
    onGamePublicState: (payload) => {
      applyGamePublicState(payload)
    },
    onGamePrivateState: (payload) => {
      applyGamePrivateState(payload)
    },
    onSettlement: (payload) => {
      applySettlement(payload)
    },
  })
  channel.connect()
  cleanupRoomChannel = () => {
    channel.disconnect()
    roomStore.roomWsConnected = false
  }
}

async function resyncRoomDetail(roomId: number) {
  if (!authStore.accessToken) {
    return
  }

  try {
    const detail = await roomsApi.getRoomDetail(authStore.accessToken, roomId)
    if (!isCurrentUserInRoom(detail)) {
      triggerServiceResetBoundary()
      return
    }
    roomStore.applyRoomUpdateEvent({
      type: 'ROOM_UPDATE',
      payload: {
        room: detail,
      },
    })
    await syncGameStateFromRoomDetail(detail)
  } catch (error) {
    if (isServiceResetBoundaryError(error)) {
      triggerServiceResetBoundary()
      return
    }
    roomStore.error = resolveErrorMessage(error)
  }
}

function resolveCurrentRoomId(): number | null {
  const raw = route.params.roomId
  const parsed = Number.parseInt(Array.isArray(raw) ? raw[0] : `${raw ?? ''}`, 10)
  if (Number.isNaN(parsed)) {
    return null
  }
  return parsed
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message
  }
  return '房间操作失败'
}

function isServiceResetBoundaryError(error: unknown): boolean {
  if (isRoomsApiError(error) && (error.status === 403 || error.status === 404)) {
    return true
  }

  if (!(error instanceof Error)) {
    return false
  }

  return error.message.includes('不在房间') || error.message.includes('房间不存在')
}

function isCurrentUserInRoom(room: { members: Array<{ user_id: number }> }): boolean {
  const selfId = authStore.user?.id
  if (!selfId) {
    return false
  }
  return room.members.some((member) => member.user_id === selfId)
}

function triggerServiceResetBoundary() {
  if (typeof window !== 'undefined') {
    window.sessionStorage.setItem(FORCE_SERVICE_RESET_KEY, '1')
    window.sessionStorage.setItem(SERVICE_RESET_NOTICE_KEY, '1')
  }
  lobbyStore.error = SERVICE_RESET_MESSAGE
  cleanupRoomChannel?.()
  cleanupRoomChannel = null
  roomStore.roomWsConnected = false
  resetGameSnapshots()
  void router.replace('/lobby')
}

async function syncGameStateFromRoomDetail(roomDetail?: RoomDetail) {
  const targetRoomDetail = roomDetail ?? roomStore.roomDetail
  if (!authStore.accessToken || !targetRoomDetail) {
    resetGameSnapshots()
    return
  }

  const gameId = targetRoomDetail.current_game_id
  if (targetRoomDetail.status !== 'playing' || gameId === null) {
    resetGameSnapshots()
    return
  }

  try {
    const response = await gamesApi.getGameState(authStore.accessToken, gameId)
    gamePublicState.value = asRecord(response.public_state)
    gamePrivateState.value = asRecord(response.private_state)
    gameLegalActions.value = asRecord(response.legal_actions)
    gameLatestEvent.value = {
      type: 'STATE_SYNC',
      payload: {
        game_id: response.game_id,
      },
    }
    if (normalizeToken(response.public_state?.phase) !== 'settlement') {
      gameSettlement.value = null
    }
  } catch (error) {
    if (isGamesApiError(error) && (error.status === 403 || error.status === 404 || error.status === 409)) {
      resetGameSnapshots()
      return
    }
    roomStore.error = resolveErrorMessage(error)
  }
}

function applyGamePublicState(payload: RoomGamePublicPayload) {
  const expectedGameId = roomStore.roomDetail?.current_game_id
  if (expectedGameId === null || expectedGameId === undefined || payload.game_id !== expectedGameId) {
    return
  }
  gamePublicState.value = asRecord(payload.public_state)
  gameLatestEvent.value = {
    type: 'GAME_PUBLIC_STATE',
    payload: {
      game_id: payload.game_id,
    },
  }
  if (normalizeToken(payload.public_state?.phase) !== 'settlement') {
    gameSettlement.value = null
  }
}

function applyGamePrivateState(payload: RoomGamePrivatePayload) {
  const expectedGameId = roomStore.roomDetail?.current_game_id
  if (expectedGameId === null || expectedGameId === undefined || payload.game_id !== expectedGameId) {
    return
  }
  gamePrivateState.value = asRecord(payload.private_state)
  gameLegalActions.value = asRecord(payload.legal_actions)
  gameLatestEvent.value = {
    type: 'GAME_PRIVATE_STATE',
    payload: {
      game_id: payload.game_id,
      self_seat: payload.self_seat,
    },
  }
}

function applySettlement(payload: Record<string, unknown>) {
  const expectedGameId = roomStore.roomDetail?.current_game_id
  const eventGameId = typeof payload.game_id === 'number' ? payload.game_id : null
  if (expectedGameId === null || expectedGameId === undefined || eventGameId === null || eventGameId !== expectedGameId) {
    return
  }
  gameSettlement.value = payload
  gameLatestEvent.value = {
    type: 'SETTLEMENT',
    payload,
  }
}

async function onIngameActionClick(actionType: string) {
  if (actionSubmitting.value) {
    return
  }

  const roomDetail = roomStore.roomDetail
  const gameId = roomDetail?.current_game_id
  if (!authStore.accessToken || !roomDetail || roomDetail.status !== 'playing' || gameId === null) {
    return
  }

  const actionIdx = findActionIndexByType(gameLegalActions.value, actionType)
  if (actionIdx < 0) {
    return
  }

  actionSubmitting.value = true
  try {
    await gamesApi.submitAction(authStore.accessToken, gameId, {
      action_idx: actionIdx,
      client_version: resolveClientVersion(gamePublicState.value),
      cover_list: null,
    })
    await syncGameStateFromRoomDetail(roomDetail)
  } catch (error) {
    if (isGamesApiError(error) && error.status === 409) {
      await syncGameStateFromRoomDetail(roomDetail)
      return
    }
    roomStore.error = resolveErrorMessage(error)
  } finally {
    actionSubmitting.value = false
  }
}

function resetGameSnapshots() {
  gamePublicState.value = null
  gamePrivateState.value = null
  gameLegalActions.value = null
  gameLatestEvent.value = null
  gameSettlement.value = null
}

function resolveClientVersion(publicState: Record<string, unknown> | null): number {
  if (!publicState) {
    return 0
  }
  const version = publicState.version
  return typeof version === 'number' && Number.isFinite(version) ? version : 0
}

function findActionIndexByType(legalActions: Record<string, unknown> | null, actionType: string): number {
  if (!legalActions) {
    return -1
  }

  const actions = (legalActions as LegalActionsLike).actions
  if (!Array.isArray(actions)) {
    return -1
  }

  return actions.findIndex((action) => {
    if (!action || typeof action !== 'object') {
      return false
    }
    return (action as LegalActionLike).type === actionType
  })
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object') {
    return value as Record<string, unknown>
  }
  return null
}

function normalizeToken(value: unknown): string {
  if (typeof value !== 'string') {
    return ''
  }

  return value.trim().toLowerCase()
}
</script>

<template>
  <main class="mx-auto max-w-3xl space-y-6 p-6">
    <h1 class="text-2xl font-bold">房间</h1>

    <p data-testid="room-ready-count" class="text-sm text-slate-700">
      {{ readyCountText }}
    </p>

    <div class="flex gap-3">
      <button
        data-testid="room-ready-toggle"
        type="button"
        class="rounded bg-slate-900 px-4 py-2 text-white"
        @click="onToggleReady"
      >
        切换准备
      </button>
      <button
        data-testid="room-leave-button"
        type="button"
        class="rounded border border-slate-300 px-4 py-2 text-slate-800"
        @click="onLeave"
      >
        离开房间
      </button>
    </div>

    <p v-if="roomStore.coldEnded" class="text-sm text-amber-700">
      {{ roomStore.coldEndMessage }}
    </p>

    <IngameShell
      :room-status="roomStore.roomDetail?.status"
      :phase="resolvedGamePhase"
      :public-state="gamePublicState ?? undefined"
      :private-state="gamePrivateState ?? undefined"
      :latest-game-event="gameLatestEvent ?? undefined"
      :settlement="gameSettlement ?? undefined"
      :legal-actions="gameLegalActions ?? undefined"
      :action-disabled-map="actionDisabledMap ?? undefined"
      @action-click="onIngameActionClick"
    />
  </main>
</template>
