export const AUTH_SESSION_STORAGE_KEY = 'xianqi.auth.session'

export interface AuthUser {
  id: number
  username: string
  createdAt?: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  expires_in: number
  user: {
    id: number
    username: string
    created_at?: string
  }
}

export interface RefreshResponse {
  access_token: string
  refresh_token?: string
  expires_in: number
}

export interface AuthApi {
  login: (payload: LoginPayload) => Promise<LoginResponse>
  register?: (payload: RegisterPayload) => Promise<LoginResponse | void>
  refresh?: (payload: { refresh_token: string }) => Promise<RefreshResponse>
}

export interface AuthStoreLike {
  user: AuthUser | null
  accessToken: string | null
  refreshToken: string | null
  accessExpireAt: number | null
  isRefreshing: boolean
  login: (payload: LoginPayload) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  refreshSession: () => Promise<boolean>
  hydrateFromStorage: () => void
  logout: () => void
}

interface AuthStoreDeps {
  api: AuthApi
  storage: Storage
  now: () => number
  onLogout: () => void
}

interface PersistedSession {
  user: AuthUser | null
  accessToken: string | null
  refreshToken: string | null
  accessExpireAt: number | null
}

let activeAuthStore: AuthStoreLike | null = null

export function createAuthStoreForTest(
  initialState: Partial<Omit<AuthStoreLike, 'login' | 'refreshSession' | 'hydrateFromStorage' | 'logout'>> = {},
  deps: Partial<AuthStoreDeps> = {},
): AuthStoreLike {
  const storage = deps.storage ?? resolveStorage()
  const now = deps.now ?? Date.now

  const store: AuthStoreLike = {
    user: initialState.user ?? null,
    accessToken: initialState.accessToken ?? null,
    refreshToken: initialState.refreshToken ?? null,
    accessExpireAt: initialState.accessExpireAt ?? null,
    isRefreshing: initialState.isRefreshing ?? false,
    async login(payload: LoginPayload) {
      if (!deps.api?.login) {
        throw new Error('auth api.login is not configured')
      }

      const response = await deps.api.login(payload)
      applyLoginResponse(store, response, now)
      persistSession(storage, store)
    },
    async register(payload: RegisterPayload) {
      if (deps.api?.register) {
        const registerResult = await deps.api.register(payload)
        if (registerResult && 'access_token' in registerResult) {
          applyLoginResponse(store, registerResult, now)
          persistSession(storage, store)
          return
        }
      }

      await store.login(payload)
    },
    async refreshSession() {
      if (store.isRefreshing) {
        return false
      }
      if (!store.refreshToken || !deps.api?.refresh) {
        return false
      }

      store.isRefreshing = true
      try {
        const response = await deps.api.refresh({ refresh_token: store.refreshToken })
        applySession(store, {
          user: store.user,
          accessToken: response.access_token,
          refreshToken: response.refresh_token ?? store.refreshToken,
          accessExpireAt: now() + response.expires_in * 1000,
        })
        persistSession(storage, store)
        return true
      } catch {
        return false
      } finally {
        store.isRefreshing = false
      }
    },
    hydrateFromStorage() {
      if (!storage) {
        return
      }

      const raw = storage.getItem(AUTH_SESSION_STORAGE_KEY)
      if (!raw) {
        return
      }

      try {
        const session = JSON.parse(raw) as PersistedSession
        applySession(store, {
          user: session.user,
          accessToken: session.accessToken,
          refreshToken: session.refreshToken,
          accessExpireAt: session.accessExpireAt,
        })
      } catch {
        storage.removeItem(AUTH_SESSION_STORAGE_KEY)
      }
    },
    logout() {
      applySession(store, {
        user: null,
        accessToken: null,
        refreshToken: null,
        accessExpireAt: null,
      })
      storage?.removeItem(AUTH_SESSION_STORAGE_KEY)
      deps.onLogout?.()
    },
  }

  return store
}

export function setActiveAuthStore(store: AuthStoreLike) {
  activeAuthStore = store
}

export function useAuthStore(): AuthStoreLike {
  if (!activeAuthStore) {
    activeAuthStore = createAuthStoreForTest()
  }
  return activeAuthStore
}

function applySession(
  store: AuthStoreLike,
  session: {
    user: AuthUser | null
    accessToken: string | null
    refreshToken: string | null
    accessExpireAt: number | null
  },
) {
  store.user = session.user
  store.accessToken = session.accessToken
  store.refreshToken = session.refreshToken
  store.accessExpireAt = session.accessExpireAt
}

function applyLoginResponse(store: AuthStoreLike, response: LoginResponse, now: () => number) {
  applySession(store, {
    user: {
      id: response.user.id,
      username: response.user.username,
      createdAt: response.user.created_at,
    },
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    accessExpireAt: now() + response.expires_in * 1000,
  })
}

function persistSession(storage: Storage | null, store: AuthStoreLike) {
  if (!storage) {
    return
  }

  const session: PersistedSession = {
    user: store.user,
    accessToken: store.accessToken,
    refreshToken: store.refreshToken,
    accessExpireAt: store.accessExpireAt,
  }
  storage.setItem(AUTH_SESSION_STORAGE_KEY, JSON.stringify(session))
}

function resolveStorage(): Storage | null {
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage
  }
  if (typeof globalThis !== 'undefined' && 'localStorage' in globalThis) {
    return globalThis.localStorage
  }
  return null
}
