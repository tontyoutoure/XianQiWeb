import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { RouterView } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'

import { createAppRouter } from '@/app/router'
import { createAuthStoreForTest } from '@/stores/auth'

const HostWithRouterView = defineComponent({
  components: { RouterView },
  template: '<RouterView />',
})

function buildAuthStoreForLoginTest(loginImpl: () => Promise<unknown>) {
  return createAuthStoreForTest(
    {},
    {
      api: {
        login: vi.fn(loginImpl),
      },
    },
  )
}

describe('M7 CT 01-03', () => {
  it('M7-CT-01 登录页提交成功后跳转大厅', async () => {
    const authStore = buildAuthStoreForLoginTest(async () => ({
      access_token: 'access-token',
      refresh_token: 'refresh-token',
      expires_in: 3600,
      user: { id: 1, username: 'alice', created_at: '2026-03-01T08:00:00Z' },
    }))
    const router = createAppRouter({ authStore })
    await router.push('/login')
    await router.isReady()

    const wrapper = mount(HostWithRouterView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    await wrapper.get('[data-testid="login-username"]').setValue('alice')
    await wrapper.get('[data-testid="login-password"]').setValue('secret')
    await wrapper.get('[data-testid="login-submit"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/lobby')
    expect(authStore.user?.username).toBe('alice')
  })

  it('M7-CT-02 登录失败展示后端错误信息', async () => {
    const authStore = buildAuthStoreForLoginTest(async () => {
      throw new Error('用户名或密码错误')
    })
    const router = createAppRouter({ authStore })
    await router.push('/login')
    await router.isReady()

    const wrapper = mount(HostWithRouterView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    await wrapper.get('[data-testid="login-username"]').setValue('alice')
    await wrapper.get('[data-testid="login-password"]').setValue('wrong')
    await wrapper.get('[data-testid="login-submit"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('用户名或密码错误')
    expect(router.currentRoute.value.fullPath).toBe('/login')
  })

  it('M7-CT-03 注册并登录入口闭环', async () => {
    const authStore = buildAuthStoreForLoginTest(async () => ({
      access_token: 'access-token-register',
      refresh_token: 'refresh-token-register',
      expires_in: 3600,
      user: { id: 2, username: 'bob', created_at: '2026-03-01T08:02:00Z' },
    }))
    const router = createAppRouter({ authStore })
    await router.push('/login')
    await router.isReady()

    const wrapper = mount(HostWithRouterView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    await wrapper.get('[data-testid="register-username"]').setValue('bob')
    await wrapper.get('[data-testid="register-password"]').setValue('secret123')
    await wrapper.get('[data-testid="register-submit"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/lobby')
    expect(authStore.user?.username).toBe('bob')
  })
})
