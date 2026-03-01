import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { RouterView } from 'vue-router'
import { describe, expect, it } from 'vitest'

import { createAppRouter } from '@/app/router'
import { createAuthStoreForTest } from '@/stores/auth'
import * as roomModule from '@/stores/room'

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

describe('M7 Stage 1.4 Red', () => {
  it('M7-WS-03 房间 WS 建连后接收 ROOM_UPDATE 初始快照', () => {
    expect(typeof roomModule.createRoomStoreForTest).toBe('function')

    const store = roomModule.createRoomStoreForTest({ roomId: 1 })
    store.applyRoomUpdateEvent({
      type: 'ROOM_UPDATE',
      payload: {
        room: {
          room_id: 1,
          status: 'waiting',
          owner_id: 1,
          current_game_id: null,
          members: [
            { user_id: 1, username: 'alice', seat: 0, ready: false, chips: 20 },
            { user_id: 2, username: 'bob', seat: 1, ready: true, chips: 20 },
          ],
        },
      },
    })

    expect(store.roomDetail).toEqual({
      room_id: 1,
      status: 'waiting',
      owner_id: 1,
      current_game_id: null,
      members: [
        { user_id: 1, username: 'alice', seat: 0, ready: false, chips: 20 },
        { user_id: 2, username: 'bob', seat: 1, ready: true, chips: 20 },
      ],
    })
  })

  it('M7-CT-06 房间页 ready 切换成功', async () => {
    const router = createAuthedRouter()
    await router.push('/rooms/1')
    await router.isReady()

    const wrapper = mount(HostWithRouterView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="room-ready-toggle"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="room-ready-count"]').text()).toContain('ready')
  })

  it('M7-CT-07 房间页 leave 成功回大厅', async () => {
    const router = createAuthedRouter()
    await router.push('/rooms/1')
    await router.isReady()

    const wrapper = mount(HostWithRouterView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    await wrapper.get('[data-testid="room-leave-button"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/lobby')
  })

  it('M7-WS-04 冷结束识别与提示', () => {
    expect(typeof roomModule.createRoomStoreForTest).toBe('function')

    const store = roomModule.createRoomStoreForTest({
      roomId: 1,
      roomDetail: {
        room_id: 1,
        status: 'playing',
        owner_id: 1,
        current_game_id: 1001,
        members: [{ user_id: 1, username: 'alice', seat: 0, ready: true, chips: 20 }],
      },
    })
    store.applyRoomUpdateEvent({
      type: 'ROOM_UPDATE',
      payload: {
        room: {
          room_id: 1,
          status: 'waiting',
          owner_id: 1,
          current_game_id: null,
          members: [{ user_id: 1, username: 'alice', seat: 0, ready: false, chips: 20 }],
        },
      },
    })

    expect(store.coldEnded).toBe(true)
    expect(store.coldEndMessage).toContain('对局结束')
  })
})
