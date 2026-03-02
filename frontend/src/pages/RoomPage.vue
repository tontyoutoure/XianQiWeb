<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { createRoomsApi, isRoomsApiError } from '@/services/rooms-api'
import { useAuthStore } from '@/stores/auth'
import { useLobbyStore } from '@/stores/lobby'
import { useRoomStore } from '@/stores/room'
import { createRoomChannel } from '@/ws/room-channel'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const lobbyStore = useLobbyStore()
const roomStore = useRoomStore()
const roomsApi = createRoomsApi()
const FORCE_SERVICE_RESET_KEY = 'xianqi.force_service_reset'
const SERVICE_RESET_NOTICE_KEY = 'xianqi.lobby_service_reset_notice'
const SERVICE_RESET_MESSAGE = '服务已重置，请重新入房'
let cleanupRoomChannel: (() => void) | null = null

const readyCountText = computed(() => {
  const members = roomStore.roomDetail?.members ?? []
  const readyCount = members.filter((member) => member.ready).length
  return `ready ${readyCount}/${members.length}`
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
  void router.replace('/lobby')
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
  </main>
</template>
