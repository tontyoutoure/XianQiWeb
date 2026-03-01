import { describe, expect, it, vi } from 'vitest'

import * as routerModule from '@/app/router'
import * as authModule from '@/stores/auth'
import * as httpModule from '@/services/http'

describe('M7 UT 01-05', () => {
  it('M7-UT-01 路由守卫：未登录访问 /lobby 跳转 /login', async () => {
    expect(typeof routerModule.createAppRouter).toBe('function')

    const router = await routerModule.createAppRouter()
    await router.push('/lobby')
    await router.isReady()

    expect(router.currentRoute.value.fullPath).toBe('/login')
  })

  it('M7-UT-02 路由守卫：access 临近过期触发 refresh 后放行', async () => {
    expect(typeof authModule.createAuthStoreForTest).toBe('function')
    expect(typeof routerModule.createAppRouter).toBe('function')

    const authStore = authModule.createAuthStoreForTest({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      accessExpireAt: Date.now() + 30_000,
    })

    const refreshSpy = vi.fn().mockResolvedValue(true)
    authStore.refreshSession = refreshSpy

    const router = await routerModule.createAppRouter({ authStore })
    await router.push('/lobby')
    await router.isReady()

    expect(refreshSpy).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.fullPath).toBe('/lobby')
  })

  it('M7-UT-03 HTTP 请求拦截器自动注入 Bearer token', async () => {
    expect(typeof httpModule.createHttpClient).toBe('function')

    const client = httpModule.createHttpClient({
      getAccessToken: () => 'access-token',
    })

    const requestConfig = await client.interceptors.request.handlers[0].fulfilled?.({
      headers: {},
      url: '/health',
    })

    expect(requestConfig?.headers?.Authorization).toBe('Bearer access-token')
  })

  it('M7-UT-04 HTTP 响应拦截器：401 时 refresh 并重放原请求', async () => {
    expect(typeof httpModule.createHttpClient).toBe('function')

    const refreshSpy = vi.fn().mockResolvedValue(true)
    const client = httpModule.createHttpClient({
      getAccessToken: () => 'new-access-token',
      refreshSession: refreshSpy,
    })

    const replaySpy = vi.fn().mockResolvedValue({
      status: 200,
      data: { ok: true },
    })
    client.request = replaySpy

    const response = await client.interceptors.response.handlers[0].rejected?.({
      config: { url: '/rooms', headers: {} },
      response: { status: 401 },
    })

    expect(refreshSpy).toHaveBeenCalledTimes(1)
    expect(replaySpy).toHaveBeenCalledTimes(1)
    expect(response?.status).toBe(200)
  })

  it('M7-UT-05 refresh 失败触发统一登出与状态清理', async () => {
    expect(typeof httpModule.createHttpClient).toBe('function')

    const logoutSpy = vi.fn()
    const client = httpModule.createHttpClient({
      getAccessToken: () => 'expired-token',
      refreshSession: vi.fn().mockResolvedValue(false),
      logout: logoutSpy,
    })

    await expect(
      client.interceptors.response.handlers[0].rejected?.({
        config: { url: '/rooms', headers: {} },
        response: { status: 401 },
      }),
    ).rejects.toBeDefined()

    expect(logoutSpy).toHaveBeenCalledTimes(1)
  })
})
