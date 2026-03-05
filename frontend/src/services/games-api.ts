import axios from 'axios'

import { createHttpClient } from '@/services/http'
import { useAuthStore } from '@/stores/auth'

interface ApiErrorPayload {
  message?: unknown
  code?: unknown
}

interface CreateGamesApiOptions {
  baseURL?: string
}

interface GameStateResponse {
  game_id: number
  self_seat: number
  public_state: Record<string, unknown>
  private_state: Record<string, unknown>
  legal_actions: Record<string, unknown> | null
}

interface SubmitActionPayload {
  action_idx: number
  client_version: number
  cover_list?: Record<string, number> | null
}

export interface GamesApiError extends Error {
  status?: number
  code?: string
}

export interface GamesApi {
  getGameState: (accessToken: string, gameId: number) => Promise<GameStateResponse>
  submitAction: (accessToken: string, gameId: number, payload: SubmitActionPayload) => Promise<void>
}

const ENV_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? undefined

export function createGamesApi(options: CreateGamesApiOptions = {}): GamesApi {
  const authStore = useAuthStore()
  const client = createHttpClient({
    baseURL: resolveBaseURL(options.baseURL),
    getAccessToken: () => authStore.accessToken,
    refreshSession: () => authStore.refreshSession(),
    logout: () => authStore.logout(),
  })
  const withFallbackAuth = (accessToken: string) => {
    if (authStore.accessToken || !accessToken) {
      return {}
    }
    return {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    }
  }

  return {
    async getGameState(accessToken: string, gameId: number): Promise<GameStateResponse> {
      try {
        const response = await client.get<GameStateResponse>(
          `/api/games/${gameId}/state`,
          withFallbackAuth(accessToken),
        )
        return response.data
      } catch (error) {
        throw toApiError(error, '对局状态加载失败')
      }
    },
    async submitAction(accessToken: string, gameId: number, payload: SubmitActionPayload): Promise<void> {
      try {
        await client.post(`/api/games/${gameId}/actions`, payload, withFallbackAuth(accessToken))
      } catch (error) {
        throw toApiError(error, '动作提交失败')
      }
    },
  }
}

export function isGamesApiError(error: unknown): error is GamesApiError {
  return error instanceof Error && ('status' in error || 'code' in error)
}

function toApiError(error: unknown, fallbackMessage: string): GamesApiError {
  if (!axios.isAxiosError(error)) {
    return new Error(fallbackMessage)
  }

  const message = (error.response?.data as ApiErrorPayload | undefined)?.message
  const nextError = new Error(fallbackMessage) as GamesApiError
  nextError.status = error.response?.status

  const code = (error.response?.data as ApiErrorPayload | undefined)?.code
  if (typeof code === 'string' && code.trim().length > 0) {
    nextError.code = code
  }

  if (typeof message === 'string' && message.trim().length > 0) {
    nextError.message = message
  }
  return nextError
}

function resolveBaseURL(override?: string): string | undefined {
  if (override) {
    return override
  }
  if (import.meta.env.DEV) {
    return undefined
  }
  return ENV_API_BASE_URL
}
