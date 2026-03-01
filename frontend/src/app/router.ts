import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import LoginPage from '@/pages/LoginPage.vue'
import { createAuthStoreForTest, setActiveAuthStore, type AuthStoreLike } from '@/stores/auth'

interface CreateRouterOptions {
  authStore?: AuthStoreLike
  refreshLeewayMs?: number
}

export function createAppRouter(options: CreateRouterOptions = {}): Router {
  const authStore = options.authStore ?? createAuthStoreForTest()
  const refreshLeewayMs = options.refreshLeewayMs ?? 60_000
  setActiveAuthStore(authStore)

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/login' },
      { path: '/login', component: LoginPage },
      { path: '/lobby', component: { template: '<div>lobby</div>' }, meta: { requiresAuth: true } },
      {
        path: '/rooms/:roomId',
        component: { template: '<div>room</div>' },
        meta: { requiresAuth: true },
      },
    ],
  })

  router.beforeEach(async (to) => {
    if (!to.meta.requiresAuth) {
      return true
    }

    if (!authStore.accessToken) {
      authStore.logout()
      return '/login'
    }

    const expireAt = authStore.accessExpireAt ?? 0
    const shouldRefresh = expireAt - Date.now() <= refreshLeewayMs
    if (!shouldRefresh) {
      return true
    }

    const refreshed = await authStore.refreshSession()
    if (!refreshed) {
      authStore.logout()
      return '/login'
    }

    return true
  })

  return router
}
