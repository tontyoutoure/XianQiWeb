import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { RouterView } from 'vue-router'
import { describe, expect, it } from 'vitest'

import { createAppRouter } from '@/app/router'
import { createAuthStoreForTest } from '@/stores/auth'
import * as lobbyModule from '@/stores/lobby'

const HostWithRouterView = defineComponent({
  components: { RouterView },
  template: '<RouterView />',
})

function createAuthedRouter() {
  const authStore = createAuthStoreForTest({
    user: { id: 1, username: 'alice' },
    accessToken: 'access-token',
    refreshToken: 'refresh-token',
    accessExpireAt: Date.now() + 3_600_000,
  })
  return createAppRouter({ authStore })
}

describe('M7 Stage 1.3 Red', () => {
  it('M7-CT-04 大厅页渲染房间列表与空态/错误态', async () => {
    const router = createAuthedRouter()
    await router.push('/lobby')
    await router.isReady()

    const wrapper = mount(HostWithRouterView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="lobby-room-table"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="lobby-empty-state"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="lobby-error-state"]').exists()).toBe(true)
  })

  it('M7-WS-01 大厅 WS 建连后接收 ROOM_LIST 全量快照', () => {
    expect(typeof lobbyModule.createLobbyStoreForTest).toBe('function')

    const store = lobbyModule.createLobbyStoreForTest()
    store.applyRoomListEvent({
      type: 'ROOM_LIST',
      payload: {
        rooms: [
          { room_id: 1, status: 'waiting', player_count: 2, ready_count: 1 },
          { room_id: 2, status: 'playing', player_count: 3, ready_count: 3 },
        ],
      },
    })

    expect(store.rooms).toEqual([
      { room_id: 1, status: 'waiting', player_count: 2, ready_count: 1 },
      { room_id: 2, status: 'playing', player_count: 3, ready_count: 3 },
    ])
  })

  it('M7-WS-02 大厅 WS 增量更新房间摘要', () => {
    expect(typeof lobbyModule.createLobbyStoreForTest).toBe('function')

    const store = lobbyModule.createLobbyStoreForTest({
      rooms: [{ room_id: 1, status: 'waiting', player_count: 1, ready_count: 0 }],
    })
    store.applyRoomListEvent({
      type: 'ROOM_UPDATE',
      payload: {
        room: { room_id: 1, status: 'waiting', player_count: 2, ready_count: 1 },
      },
    })

    expect(store.rooms).toEqual([{ room_id: 1, status: 'waiting', player_count: 2, ready_count: 1 }])
  })

  it('M7-CT-05 点击房间行 join 后跳到房间页', async () => {
    const router = createAuthedRouter()
    await router.push('/lobby')
    await router.isReady()

    const wrapper = mount(HostWithRouterView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    await wrapper.get('[data-testid="lobby-join-room-1"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/rooms/1')
  })
})
