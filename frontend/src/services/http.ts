import axios, { type AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

export interface HttpClientOptions {
  baseURL?: string
  getAccessToken?: () => string | null | undefined
  refreshSession?: () => Promise<boolean>
  logout?: () => void
}

type RetryableConfig = InternalAxiosRequestConfig & {
  __retriedAfterRefresh?: boolean
}

export function createHttpClient(options: HttpClientOptions = {}): AxiosInstance {
  const client = axios.create({
    baseURL: options.baseURL,
  })

  client.interceptors.request.use((config) => {
    const accessToken = options.getAccessToken?.()
    if (!accessToken) {
      return config
    }

    config.headers = config.headers ?? {}
    ;(config.headers as Record<string, string>).Authorization = `Bearer ${accessToken}`
    return config
  })

  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const status = error.response?.status
      const requestConfig = (error.config ?? {}) as RetryableConfig

      if (status !== 401) {
        throw error
      }
      if (requestConfig.__retriedAfterRefresh) {
        options.logout?.()
        throw error
      }

      const refreshed = (await options.refreshSession?.()) ?? false
      if (!refreshed) {
        options.logout?.()
        throw error
      }

      requestConfig.__retriedAfterRefresh = true
      const refreshedToken = options.getAccessToken?.()
      if (refreshedToken) {
        requestConfig.headers = requestConfig.headers ?? {}
        ;(requestConfig.headers as Record<string, string>).Authorization = `Bearer ${refreshedToken}`
      }

      return client.request(requestConfig)
    },
  )

  return client
}
