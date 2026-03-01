import axios from 'axios'

import type { AuthApi, LoginPayload, LoginResponse, RefreshResponse, RegisterPayload } from '@/stores/auth'

interface ApiErrorPayload {
  message?: unknown
}

interface CreateAuthApiOptions {
  baseURL?: string
}

const ENV_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? undefined

export function createAuthApi(options: CreateAuthApiOptions = {}): AuthApi {
  const client = axios.create({
    baseURL: resolveBaseURL(options.baseURL),
  })

  return {
    async login(payload: LoginPayload): Promise<LoginResponse> {
      try {
        const response = await client.post<LoginResponse>('/api/auth/login', payload)
        return response.data
      } catch (error) {
        throw toApiError(error, '登录失败，请稍后重试')
      }
    },
    async register(payload: RegisterPayload): Promise<LoginResponse> {
      try {
        const response = await client.post<LoginResponse>('/api/auth/register', payload)
        return response.data
      } catch (error) {
        throw toApiError(error, '注册失败，请稍后重试')
      }
    },
    async refresh(payload: { refresh_token: string }): Promise<RefreshResponse> {
      try {
        const response = await client.post<RefreshResponse>('/api/auth/refresh', payload)
        return response.data
      } catch (error) {
        throw toApiError(error, '会话刷新失败')
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
