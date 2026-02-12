# components/lobby/LobbyCard.vue
<template>
  <div class="lobby-card p-4 border rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-pointer">
    <div class="flex justify-between items-center mb-2">
      <h3 class="text-lg font-semibold">Lobby #{{ lobby.id.slice(0,8) }}</h3>
      <span class="text-sm text-gray-500">{{ playerCount }}/3</span>
    </div>
    
    <div class="players-list space-y-2">
      <div v-for="player in lobby.players" :key="player" class="flex items-center">
        <span class="flex-1">{{ player }}</span>
        <span v-if="player === lobby.host" class="text-sm text-blue-500">(Host)</span>
        <span v-if="lobby.chip_count" class="text-sm text-gray-600">
          {{ lobby.chip_count }} chips
        </span>
      </div>
    </div>

    <div class="mt-4 flex justify-end">
      <button 
        v-if="!isInLobby"
        @click="$emit('join', lobby.id)"
        class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 active:bg-blue-700"
      >
        Join
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from 'vuex'

const props = defineProps<{
  lobby: {
    id: string
    host: string
    players: string[]
    chip_count?: number
  }
}>()

defineEmits<{
  (e: 'join', lobbyId: string): void
}>()

const store = useStore()
const playerCount = computed(() => props.lobby.players.length)
const isInLobby = computed(() => {
  const currentLobbyId = store.state.user.currentLobbyId
  return currentLobbyId === props.lobby.id
})
</script>