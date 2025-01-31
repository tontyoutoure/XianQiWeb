<!-- src/views/LobbyListPage.vue -->
<template>
  <div class="lobby-list-container">
    <h1>游戏大厅</h1>
    <div v-if="connectionError" class="error-message">
      {{ connectionError }}
      <Button text="返回" @click="handleDisconnect" />
    </div>
    <!-- TODO: Add lobby list here -->
    <div class="connection-status">
      状态: {{ connectionStatus }}
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, onUnmounted, watch } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'
import Button from '@/components/common/Button.vue'

export default defineComponent({
  name: 'LobbyListPage',
  components: {
    Button
  },
  setup() {
    const store = useStore()
    const router = useRouter()
    const connectionError = ref('')
    const { connectionStatus, connectionState, startHeartbeat, stopHeartbeat, disconnect } = useWebSocket()

    // Watch connection state for errors
    watch(connectionState, (state) => {
      if (state === 'error' || state === 'disconnected') {
        connectionError.value = '连接已断开，请重新连接'
      } else {
        connectionError.value = ''
      }
    })

    onMounted(() => {
      // If we're connected, start heartbeat
      if (connectionState.value === 'connected') {
        startHeartbeat()
      }
    })

    onUnmounted(() => {
      stopHeartbeat()
    })

    const handleDisconnect = async () => {
      disconnect()
      router.push('/')
    }

    return {
      connectionError,
      connectionStatus,
      handleDisconnect
    }
  }
})
</script>

<style scoped>
.lobby-list-container {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.error-message {
  color: #ff4444;
  margin-bottom: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  align-items: center;
}

.connection-status {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 8px 16px;
  background-color: #f5f5f5;
  border-radius: 4px;
  font-size: 14px;
}
</style>