import { describe, expect, it, vi } from 'vitest'

import * as authModule from '@/stores/auth'

describe('M7 UT 06-07', () => {
  it('M7-UT-06 authStore.login 成功后写入会话态', async () => {
    expect(typeof authModule.createAuthStoreForTest).toBe('function')

    const store = authModule.createAuthStoreForTest(
      {},
      {
        api: {
          login: vi.fn().mockResolvedValue({
            access_token: 'access-token',
            refresh_token: 'refresh-token',
            expires_in: 3600,
            user: { id: 1, username: 'alice', created_at: '2026-03-01T07:00:00Z' },
          }),
        },
      },
    )

    await store.login({ username: 'alice', password: 'secret' })

    expect(store.user?.username).toBe('alice')
    expect(store.accessToken).toBe('access-token')
    expect(store.refreshToken).toBe('refresh-token')
    expect(typeof store.accessExpireAt).toBe('number')
    expect((store.accessExpireAt ?? 0) > Date.now()).toBe(true)
  })

  it('M7-UT-07 authStore.hydrateFromStorage 可恢复会话', () => {
    expect(typeof authModule.createAuthStoreForTest).toBe('function')

    const memoryStorage = createMemoryStorage()
    memoryStorage.setItem(
      'xianqi.auth.session',
      JSON.stringify({
        user: { id: 2, username: 'bob', createdAt: '2026-03-01T07:01:00Z' },
        accessToken: 'restored-access',
        refreshToken: 'restored-refresh',
        accessExpireAt: Date.now() + 3_600_000,
      }),
    )

    const store = authModule.createAuthStoreForTest({}, { storage: memoryStorage })
    store.hydrateFromStorage()

    expect(store.user?.username).toBe('bob')
    expect(store.accessToken).toBe('restored-access')
    expect(store.refreshToken).toBe('restored-refresh')
    expect(store.accessExpireAt).not.toBeNull()
  })
})

function createMemoryStorage(): Storage {
  const map = new Map<string, string>()

  return {
    get length() {
      return map.size
    },
    clear() {
      map.clear()
    },
    getItem(key: string) {
      return map.get(key) ?? null
    },
    key(index: number) {
      return Array.from(map.keys())[index] ?? null
    },
    removeItem(key: string) {
      map.delete(key)
    },
    setItem(key: string, value: string) {
      map.set(key, value)
    },
  }
}
