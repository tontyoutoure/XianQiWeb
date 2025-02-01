// src/composables/useWebSocket.ts
import { ref, computed } from 'vue'
import store from '@/store'  // Import store

const HEARTBEAT_INTERVAL = 5000 // 5 seconds

// Shared state between all instances
const connectionState = ref<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected')
let wsInstance: WebSocket | null = null
let heartbeatIntervalId: number | null = null

export function useWebSocket() {
  const connectionStatus = computed(() => {
    switch (connectionState.value) {
      case 'connected':
        return '已连接'
      case 'connecting':
        return '连接中...'
      case 'error':
        return '连接错误'
      default:
        return '未连接'
    }
  })

  const connect = async (playerName: string) => {
    if (wsInstance?.readyState === WebSocket.OPEN) {
      connectionState.value = 'connected'
      return Promise.resolve() // Already connected
    }

    return new Promise<void>((resolve, reject) => {
      connectionState.value = 'connecting'
      
      const apiUrl = import.meta.env.VITE_API_URL || window.location.origin
      const wsUrl = apiUrl.replace(/^http/, 'ws')
      
      wsInstance = new WebSocket(`${wsUrl}/ws/${playerName}`)

      wsInstance.onopen = () => {
        connectionState.value = 'connected'
        resolve()
      }

      wsInstance.onerror = (error) => {
        connectionState.value = 'error'
        reject(error)
      }

      wsInstance.onclose = () => {
        connectionState.value = 'disconnected'
        stopHeartbeat()
        wsInstance = null
      }

      wsInstance.onmessage = (event) => {
        const message = JSON.parse(event.data)
        handleMessage(message)
      }
    })
  }

  const disconnect = () => {
    if (wsInstance) {
      wsInstance.close()
      wsInstance = null
    }
    connectionState.value = 'disconnected'
    stopHeartbeat()
  }

  const startHeartbeat = () => {
    if (heartbeatIntervalId) return
    if (!wsInstance || wsInstance.readyState !== WebSocket.OPEN) {
      console.warn('Cannot start heartbeat: WebSocket is not connected')
      return
    }

    heartbeatIntervalId = window.setInterval(() => {
      if (wsInstance?.readyState === WebSocket.OPEN) {
        wsInstance.send(JSON.stringify({ type: 'heartbeat' }))
      } else {
        stopHeartbeat()
        connectionState.value = 'disconnected'
      }
    }, HEARTBEAT_INTERVAL)
  }

  const stopHeartbeat = () => {
    if (heartbeatIntervalId) {
      clearInterval(heartbeatIntervalId)
      heartbeatIntervalId = null
    }
  }

  const handleMessage = (message: any) => {
    switch (message.type) {
      case 'connection_established':
        console.log('Connection established:', message)
        connectionState.value = 'connected'
        break
      case 'heartbeat_ack':
        // Optional: handle heartbeat acknowledgment
        break
      default:
        console.log('Unhandled message type:', message)
    }
  }

  const send = (message: any) => {
    if (wsInstance?.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify(message))
    } else {
      console.error('Cannot send message: WebSocket is not connected')
      connectionState.value = 'disconnected'
    }
  }

  return {
    connect,
    disconnect,
    startHeartbeat,
    stopHeartbeat,
    connectionStatus,
    connectionState,
    send
  }
}