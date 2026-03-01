import { createMemoryHistory, createRouter, createWebHistory, type Router } from 'vue-router'

import LobbyPage from '@/pages/LobbyPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import RoomPage from '@/pages/RoomPage.vue'
import { createAuthStoreForTest, setActiveAuthStore, type AuthStoreLike } from '@/stores/auth'

interface CreateRouterOptions {
  authStore?: AuthStoreLike
  refreshLeewayMs?: number
  history?: 'memory' | 'web'
}

export function createAppRouter(options: CreateRouterOptions = {}): Router {
  const authStore = options.authStore ?? createAuthStoreForTest()
  const refreshLeewayMs = options.refreshLeewayMs ?? 60_000
  const history = options.history === 'web' ? createWebHistory() : createMemoryHistory()
  setActiveAuthStore(authStore)

  const router = createRouter({
    history,
    routes: [
      { path: '/', redirect: '/login' },
      { path: '/login', component: LoginPage },
      { path: '/lobby', component: LobbyPage, meta: { requiresAuth: true } },
      {
        path: '/rooms/:roomId',
        component: RoomPage,
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
