import axios from 'axios'

import type { RoomDetail } from '@/stores/room'
import type { RoomSummary } from '@/stores/lobby'

interface ApiErrorPayload {
  message?: unknown
}

interface CreateRoomsApiOptions {
  baseURL?: string
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
  const client = axios.create({
    baseURL: resolveBaseURL(options.baseURL),
  })

  return {
    async listRooms(accessToken: string): Promise<RoomSummary[]> {
      try {
        const response = await client.get<RoomSummary[]>('/api/rooms', {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        })
        return response.data
      } catch (error) {
        throw toApiError(error, '房间列表加载失败')
      }
    },
    async getRoomDetail(accessToken: string, roomId: number): Promise<RoomDetail> {
      try {
        const response = await client.get<RoomDetail>(`/api/rooms/${roomId}`, {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        })
        return response.data
      } catch (error) {
        throw toApiError(error, '房间详情加载失败')
      }
    },
    async joinRoom(accessToken: string, roomId: number): Promise<RoomDetail> {
      try {
        const response = await client.post<RoomDetail>(
          `/api/rooms/${roomId}/join`,
          {},
          {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          },
        )
        return response.data
      } catch (error) {
        throw toApiError(error, '加入房间失败')
      }
    },
    async leaveRoom(accessToken: string, roomId: number): Promise<{ ok: true }> {
      try {
        const response = await client.post<{ ok: true }>(
          `/api/rooms/${roomId}/leave`,
          {},
          {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          },
        )
        return response.data
      } catch (error) {
        throw toApiError(error, '离开房间失败')
      }
    },
    async setReady(accessToken: string, roomId: number, ready: boolean): Promise<RoomDetail> {
      try {
        const response = await client.post<RoomDetail>(
          `/api/rooms/${roomId}/ready`,
          { ready },
          {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          },
        )
        return response.data
      } catch (error) {
        throw toApiError(error, '准备状态更新失败')
      }
    },
  }
}

function toApiError(error: unknown, fallbackMessage: string): Error {
  if (!axios.isAxiosError(error)) {
    return new Error(fallbackMessage)
  }

  const message = (error.response?.data as ApiErrorPayload | undefined)?.message
  if (typeof message === 'string' && message.trim().length > 0) {
    return new Error(message)
  }
  return new Error(fallbackMessage)
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
