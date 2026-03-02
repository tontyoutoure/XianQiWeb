import axios from 'axios'

import { createHttpClient } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import type { RoomDetail } from '@/stores/room'
import type { RoomSummary } from '@/stores/lobby'

interface ApiErrorPayload {
  message?: unknown
  code?: unknown
}

interface CreateRoomsApiOptions {
  baseURL?: string
}

export interface RoomsApiError extends Error {
  status?: number
  code?: string
}

export interface RoomsApi {
  listRooms: (accessToken: string) => Promise<RoomSummary[]>
  getRoomDetail: (accessToken: string, roomId: number) => Promise<RoomDetail>
  joinRoom: (accessToken: string, roomId: number) => Promise<RoomDetail>
  leaveRoom: (accessToken: string, roomId: number) => Promise<{ ok: true }>
  setReady: (accessToken: string, roomId: number, ready: boolean) => Promise<RoomDetail>
}

const ENV_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? undefined

export function createRoomsApi(options: CreateRoomsApiOptions = {}): RoomsApi {
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
    async listRooms(accessToken: string): Promise<RoomSummary[]> {
      try {
        const response = await client.get<RoomSummary[]>('/api/rooms', withFallbackAuth(accessToken))
        return response.data
      } catch (error) {
        throw toApiError(error, '房间列表加载失败')
      }
    },
    async getRoomDetail(accessToken: string, roomId: number): Promise<RoomDetail> {
      try {
        const response = await client.get<RoomDetail>(`/api/rooms/${roomId}`, withFallbackAuth(accessToken))
        return response.data
      } catch (error) {
        throw toApiError(error, '房间详情加载失败')
      }
    },
    async joinRoom(accessToken: string, roomId: number): Promise<RoomDetail> {
      try {
        const response = await client.post<RoomDetail>(`/api/rooms/${roomId}/join`, {}, withFallbackAuth(accessToken))
        return response.data
      } catch (error) {
        throw toApiError(error, '加入房间失败')
      }
    },
    async leaveRoom(accessToken: string, roomId: number): Promise<{ ok: true }> {
      try {
        const response = await client.post<{ ok: true }>(`/api/rooms/${roomId}/leave`, {}, withFallbackAuth(accessToken))
        return response.data
      } catch (error) {
        throw toApiError(error, '离开房间失败')
      }
    },
    async setReady(accessToken: string, roomId: number, ready: boolean): Promise<RoomDetail> {
      try {
        const response = await client.post<RoomDetail>(`/api/rooms/${roomId}/ready`, { ready }, withFallbackAuth(accessToken))
        return response.data
      } catch (error) {
        throw toApiError(error, '准备状态更新失败')
      }
    },
  }
}

export function isRoomsApiError(error: unknown): error is RoomsApiError {
  return error instanceof Error && ('status' in error || 'code' in error)
}

function toApiError(error: unknown, fallbackMessage: string): RoomsApiError {
  if (!axios.isAxiosError(error)) {
    return new Error(fallbackMessage)
  }

  const message = (error.response?.data as ApiErrorPayload | undefined)?.message
  const nextError = new Error(fallbackMessage) as RoomsApiError
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
