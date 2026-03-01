export type WsConnectionState = 'disconnected' | 'reconnecting' | 'connected'

export interface WsStoreForTest {
  markDisconnected: () => void
  attemptReconnect: () => Promise<void>
  connectionState: () => WsConnectionState
  fallbackRestSyncCount: () => number
}

export function createWsStoreForTest(): WsStoreForTest {
  let state: WsConnectionState = 'connected'
  let restSyncCount = 0

  return {
    markDisconnected() {
      state = 'disconnected'
    },
    async attemptReconnect() {
      state = 'reconnecting'
      await Promise.resolve()
      state = 'connected'
      restSyncCount += 1
    },
    connectionState() {
      return state
    },
    fallbackRestSyncCount() {
      return restSyncCount
    },
  }
}
