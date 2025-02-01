# src/views/LobbyPage.vue
<template>
  <div class="lobby-page-container">
    <div class="max-w-2xl mx-auto p-6">
      <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold">房间 #{{ lobbyId?.slice(0, 8) }}</h1>
        <button
          @click="handleLeaveLobby"
          class="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600"
        >
          离开房间
        </button>
      </div>

      <!-- Player List -->
      <div class="bg-white rounded-lg shadow p-6 mb-6">
        <h2 class="text-lg font-semibold mb-4">玩家列表</h2>
        <div class="space-y-3">
          <div
            v-for="player in currentLobby?.players"
            :key="player"
            class="flex items-center justify-between p-3 bg-gray-50 rounded"
          >
            <div class="flex items-center">
              <span>{{ player }}</span>
              <span
                v-if="player === currentLobby.host"
                class="ml-2 text-sm text-blue-500"
              >(房主)</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Game Settings (visible only to host) -->
      <div
        v-if="isHost"
        class="bg-white rounded-lg shadow p-6 mb-6"
      >
        <h2 class="text-lg font-semibold mb-4">游戏设置</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-2">初始筹码数</label>
            <div class="grid grid-cols-5 gap-2">
              <button
                v-for="count in [10, 15, 20, 25, 30]"
                :key="count"
                @click="updateChipCount(count)"
                :class="[
                  'p-2 text-center rounded border',
                  currentLobby?.chip_count === count
                    ? 'bg-blue-500 text-white border-blue-600'
                    : 'border-gray-300 hover:border-blue-500'
                ]"
              >
                {{ count }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useStore } from 'vuex'
import { useRouter, useRoute } from 'vue-router'

const store = useStore()
const router = useRouter()
const route = useRoute()

const lobbyId = computed(() => route.params.id as string)
const currentLobby = computed(() => 
  store.state.lobby.lobbies.find(l => l.id === lobbyId.value)
)
const isHost = computed(() => 
  currentLobby.value?.host === store.state.user.playerName
)

onMounted(async () => {
  // Fetch initial lobby data
  await store.dispatch('lobby/fetchLobbies')
})

const handleLeaveLobby = async () => {
  try {
    await store.dispatch('lobby/leaveLobby', lobbyId.value)
    await store.dispatch('user/leaveLobby')
    router.push('/lobbies')
  } catch (error) {
    console.error('Failed to leave lobby:', error)
  }
}

const updateChipCount = async (chipCount: number) => {
  if (!isHost.value) return
  try {
    await fetch(`/api/lobby/${lobbyId.value}/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chip_count: chipCount })
    })
    await store.dispatch('lobby/fetchLobbies')
  } catch (error) {
    console.error('Failed to update chip count:', error)
  }
}
</script>