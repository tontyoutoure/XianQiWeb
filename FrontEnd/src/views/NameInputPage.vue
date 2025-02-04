<!-- src/views/NameInputPage.vue -->
<template>
  <div class="name-input-container">
    <h1>掀棋</h1>
    <div class="input-wrapper">
      <Input
        v-model="playerName"
        placeholder="请输入姓名"
        :error="errorMessage"
        :disabled="isConnecting"
      />
      <Button
        :text="isConnecting ? '连接中...' : '继续'"
        :disabled="!playerName.trim() || isConnecting"
        @click="handleSubmit"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'
import Button from '@/components/common/Button.vue'
import Input from '@/components/common/Input.vue'

export default defineComponent({
  name: 'NameInputPage',
  components: {
    Button,
    Input
  },
  setup() {
    const store = useStore()
    const router = useRouter()
    const playerName = ref('')
    const errorMessage = ref('')
    const isConnecting = ref(false)
    const { connect, connectionState, errorType } = useWebSocket()

    const handleSubmit = async () => {
      if (isConnecting.value) return
      
      isConnecting.value = true
      errorMessage.value = ''
      
      try {
        // Store the name in Vuex
        await store.dispatch('user/setPlayerName', playerName.value.trim())
        
        // Establish WebSocket connection
        await connect(playerName.value.trim())
        console.log('finding connection state')
        while (true) {
          console.log('connection state:', connectionState.value)
          if (connectionState.value === 'connected') {
            console.log('Connected!')
            break
          }
          else if (connectionState.value === 'disconnected') 
          {
            console.log('Disconnected!')
            if (errorType.value === 'error_player_already_exist')
              {
                console.log('Error: player already exists')
                throw new Error('玩家已存在，请更换姓名')
              }
            else {
              console.log('Error: connection failed_')
              throw new Error('连接失败，请重试')
            }

          }
          //sleep for a while
          else if (connectionState.value=== 'connecting')
          {
            console.log('Connecting...')
            await new Promise(resolve => setTimeout(resolve, 100))

          }
          else
          {
            console.log('Error: connection failed')
            throw new Error('连接失败，请重试')
          }
        }
        // Only navigate after successful connection
        router.push('/lobby-list')
      } catch (error) {
        errorMessage.value = error instanceof Error ? error.message : '连接失败，请重试'
        console.error('Error:', error)
        // Clear Vuex state if connection failed
        store.dispatch('user/setPlayerName', '')
      } finally {
        isConnecting.value = false
      }
    }

    return {
      playerName,
      errorMessage,
      isConnecting,
      handleSubmit
    }
  }
})
</script>

<style scoped>
.name-input-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 20px;
}

h1 {
  margin-bottom: 2rem;
  color: #333;
}

.input-wrapper {
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>