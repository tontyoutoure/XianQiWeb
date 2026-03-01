<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useLobbyStore } from '@/stores/lobby'
import { useRoomStore } from '@/stores/room'

const router = useRouter()
const lobbyStore = useLobbyStore()
const roomStore = useRoomStore()
const FORCE_SERVICE_RESET_KEY = 'xianqi.force_service_reset'

const readyCountText = computed(() => {
  const members = roomStore.roomDetail?.members ?? []
  const readyCount = members.filter((member) => member.ready).length
  return `ready ${readyCount}/${members.length}`
})

onMounted(() => {
  const shouldForceReset =
    typeof window !== 'undefined' && window.sessionStorage.getItem(FORCE_SERVICE_RESET_KEY) === '1'
  if (!shouldForceReset) {
    return
  }

  window.sessionStorage.removeItem(FORCE_SERVICE_RESET_KEY)
  lobbyStore.error = '服务已重置，请重新入房'
  void router.replace('/lobby')
})

function onToggleReady() {
  roomStore.toggleReady()
}

async function onLeave() {
  await router.push('/lobby')
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
