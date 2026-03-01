import axios from 'axios'

import type { RoomSummary } from '@/stores/lobby'

interface ApiErrorPayload {
  message?: unknown
}

interface CreateRoomsApiOptions {
  baseURL?: string
}

export interface RoomsApi {
  listRooms: (accessToken: string) => Promise<RoomSummary[]>
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
