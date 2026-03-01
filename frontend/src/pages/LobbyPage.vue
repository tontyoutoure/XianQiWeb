<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { createRoomsApi } from '@/services/rooms-api'
import { useAuthStore } from '@/stores/auth'
import { useLobbyStore } from '@/stores/lobby'

const router = useRouter()
const authStore = useAuthStore()
const lobbyStore = useLobbyStore()
const roomsApi = createRoomsApi()

const rooms = computed(() => lobbyStore.rooms)

onMounted(() => {
  if (import.meta.env.MODE === 'test') {
    return
  }
  void loadRooms()
})

async function loadRooms() {
  if (!authStore.accessToken) {
    lobbyStore.error = '未登录或会话已失效'
    return
  }

  lobbyStore.loading = true
  lobbyStore.error = null
  try {
    lobbyStore.rooms = await roomsApi.listRooms(authStore.accessToken)
    lobbyStore.lastSyncAt = Date.now()
  } catch (error) {
    lobbyStore.error = resolveErrorMessage(error)
  } finally {
    lobbyStore.loading = false
  }
}

async function onJoinRoom(roomId: number) {
  await router.push(`/rooms/${roomId}`)
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message
  }
  return '房间列表加载失败'
}
</script>

<template>
  <main class="mx-auto max-w-4xl space-y-6 p-6">
    <h1 class="text-2xl font-bold">大厅</h1>

    <section
      data-testid="lobby-error-state"
      class="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700"
    >
      {{ lobbyStore.error ?? '当前无错误' }}
    </section>

    <section
      data-testid="lobby-empty-state"
      class="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600"
    >
      当前房间数量：{{ rooms.length }}
    </section>

    <table data-testid="lobby-room-table" class="w-full border-collapse rounded border">
      <thead>
        <tr class="bg-slate-100 text-left">
          <th class="border px-3 py-2">房间</th>
          <th class="border px-3 py-2">状态</th>
          <th class="border px-3 py-2">人数</th>
          <th class="border px-3 py-2">就绪</th>
          <th class="border px-3 py-2">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="room in rooms" :key="room.room_id">
          <td class="border px-3 py-2">{{ room.room_id }}</td>
          <td class="border px-3 py-2">{{ room.status }}</td>
          <td class="border px-3 py-2">{{ room.player_count }}</td>
          <td class="border px-3 py-2">{{ room.ready_count }}</td>
          <td class="border px-3 py-2">
            <button
              :data-testid="`lobby-join-room-${room.room_id}`"
              type="button"
              class="rounded bg-slate-900 px-3 py-1.5 text-white"
              @click="onJoinRoom(room.room_id)"
            >
              加入
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </main>
</template>
