import { describe, expect, it } from 'vitest'

import * as wsStoreModule from '@/stores/ws'
import * as wsClientModule from '@/ws/ws-client'

interface WsClientForHeartbeatTest {
  bindSocket: (socket: { send: (raw: string) => void }) => void
  onRawMessage: (raw: string) => void
  isConnectionAlive: () => boolean
}

describe('M7 Stage 1.5 Red', () => {
  it('M7-WS-05 房间/大厅 WS 心跳 PING/PONG 保活', () => {
    const wsClientExports = wsClientModule as unknown as Record<string, unknown>
    expect(typeof wsClientExports.createWsClientForTest).toBe('function')

    if (typeof wsClientExports.createWsClientForTest !== 'function') {
      return
    }

    const sentFrames: Array<{ v: number; type: string; payload: Record<string, never> }> = []
    const client = wsClientExports.createWsClientForTest() as WsClientForHeartbeatTest

    client.bindSocket({
      send(raw: string) {
        sentFrames.push(JSON.parse(raw))
      },
    })

    client.onRawMessage(JSON.stringify({ v: 1, type: 'PING', payload: {} }))

    expect(sentFrames).toEqual([{ v: 1, type: 'PONG', payload: {} }])
    expect(client.isConnectionAlive()).toBe(true)
  })

  it('M7-WS-06 WS 断线自动重连 + REST 拉态兜底', async () => {
    const wsStoreExports = wsStoreModule as unknown as Record<string, unknown>
    expect(typeof wsStoreExports.createWsStoreForTest).toBe('function')

    if (typeof wsStoreExports.createWsStoreForTest !== 'function') {
      return
    }

    const wsStore = wsStoreExports.createWsStoreForTest() as {
      markDisconnected: () => void
      attemptReconnect: () => Promise<void>
      connectionState: () => string
      fallbackRestSyncCount: () => number
    }

    wsStore.markDisconnected()
    await wsStore.attemptReconnect()

    expect(wsStore.connectionState()).toBe('connected')
    expect(wsStore.fallbackRestSyncCount()).toBeGreaterThan(0)
  })
})
