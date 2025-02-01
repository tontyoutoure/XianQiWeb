# src/views/LobbyListPage.vue
<template>
  <div class="min-h-screen bg-gray-50">
    <div class="lobby-list-container max-w-6xl mx-auto bg-white shadow-lg rounded-lg p-6 my-8">
      <div class="flex justify-between items-center mb-8 border-b pb-4">
        <h1 class="text-2xl font-bold text-gray-800">游戏大厅</h1>
        <Button 
          text="创建房间" 
          @click="showCreateDialog = true"
          type="primary"
        />
      </div>

      <div v-if="connectionError" class="error-message">
        {{ connectionError }}
        <Button text="返回" @click="handleDisconnect" />
      </div>

      <div v-if="fetchError" class="error-message">
        获取房间列表失败: {{ fetchError }}
      </div>

      <!-- Debug info -->
      <div v-if="isDevelopment" class="mb-6 p-4 bg-gray-100 rounded-lg text-sm">
        <p>Connection Status: {{ connectionStatus }}</p>
        <p>Number of Lobbies: {{ lobbies.length }}</p>
        <pre class="mt-2 overflow-auto">{{ JSON.stringify(lobbies, null, 2) }}</pre>
      </div>

      <!-- Lobby List -->
      <div v-if="lobbies.length === 0" class="text-center py-12">
        <div class="text-gray-500 mb-4">暂无可用房间</div>
        <Button 
          text="创建第一个房间" 
          @click="showCreateDialog = true"
          type="primary"
        />
      </div>
      
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <LobbyCard
          v-for="lobby in lobbies"
          :key="lobby.id"
          :lobby="lobby"
          @join="handleJoinLobby"
        />
      </div>

      <!-- Create Lobby Dialog -->
      <CreateLobbyDialog
        :is-open="showCreateDialog"
        @close="showCreateDialog = false"
        @create="handleCreateLobby"
      />

      <!-- Connection Status -->
      <div class="connection-status">
        <span class="inline-flex items-center gap-2">
          <span class="w-2 h-2 rounded-full" 
                :class="connectionState === 'connected' ? 'bg-green-500' : 'bg-red-500'">
          </span>
          {{ connectionStatus }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'
import Button from '@/components/common/Button.vue'
import LobbyCard from '@/components/lobby/LobbyCard.vue'
import CreateLobbyDialog from '@/components/lobby/CreateLobbyDialog.vue'

const store = useStore()
const router = useRouter()
const connectionError = ref('')
const fetchError = ref('')
const showCreateDialog = ref(false)
const { connectionStatus, connectionState, startHeartbeat, stopHeartbeat, disconnect } = useWebSocket()

// Development mode check
const isDevelopment = computed(() => process.env.NODE_ENV === 'development')

// Watch connection state for errors
watch(connectionState, (state) => {
  if (state === 'error' || state === 'disconnected') {
    connectionError.value = '连接已断开，请重新连接'
  } else {
    connectionError.value = ''
  }
})

const lobbies = computed(() => {
  console.log('Current store state:', store.state.lobby)
  return store.state.lobby.lobbies
})

// Fetch lobbies on component mount and start polling
const fetchLobbies = async () => {
  try {
    console.log('Fetching lobbies...')
    await store.dispatch('lobby/fetchLobbies')
    console.log('Lobbies fetched:', store.state.lobby.lobbies)
  } catch (error) {
    console.error('Error fetching lobbies:', error)
    fetchError.value = error instanceof Error ? error.message : '未知错误'
  }
}

onMounted(async () => {
  console.log('Component mounted')
  if (connectionState.value === 'connected') {
    startHeartbeat()
  }
  await fetchLobbies()
  
  // Start polling for lobby updates
  const pollInterval = setInterval(fetchLobbies, 5000)
  onUnmounted(() => {
    clearInterval(pollInterval)
  })
})

onUnmounted(() => {
  stopHeartbeat()
})

const handleDisconnect = async () => {
  disconnect()
  router.push('/')
}

const handleCreateLobby = async (chipCount: number) => {
  try {
    console.log('Creating lobby with chip count:', chipCount)
    const newLobby = await store.dispatch('lobby/createLobby', chipCount)
    console.log('New lobby created:', newLobby)
    await store.dispatch('user/joinLobby', newLobby.id)
    router.push(`/lobby/${newLobby.id}`)
  } catch (error) {
    console.error('Failed to create lobby:', error)
    fetchError.value = error instanceof Error ? error.message : '创建房间失败'
  }
}

const handleJoinLobby = async (lobbyId: string) => {
  try {
    console.log('Joining lobby:', lobbyId)
    await store.dispatch('lobby/joinLobby', lobbyId)
    await store.dispatch('user/joinLobby', lobbyId)
    router.push(`/lobby/${lobbyId}`)
  } catch (error) {
    console.error('Failed to join lobby:', error)
    fetchError.value = error instanceof Error ? error.message : '加入房间失败'
  }
}
</script>

<style scoped>
.error-message {
  @apply bg-red-100 text-red-700 p-4 rounded-lg mb-4 flex flex-col items-center gap-4;
}

.connection-status {
  @apply fixed bottom-4 right-4 px-4 py-2 bg-white shadow-md rounded-lg text-sm;
}
</style>