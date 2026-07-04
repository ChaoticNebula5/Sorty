import axios from 'axios'
import { getAdminToken, clearAdminToken, dispatchAuthLocked } from '@/lib/auth'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export function resolveApiUrl(url: string): string {
  if (url.startsWith('http')) {
    return url
  }

  const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')
  if (url.startsWith('/api')) {
    if (/^https?:\/\//i.test(baseUrl)) {
      const apiRoot = baseUrl.endsWith('/api') ? baseUrl.slice(0, -4) : baseUrl
      return `${apiRoot}${url}`
    }
    return url
  }

  return `${baseUrl}${url.startsWith('/') ? url : `/${url}`}`
}

apiClient.interceptors.request.use((config) => {
  const token = getAdminToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearAdminToken()
      dispatchAuthLocked()
    }
    return Promise.reject(error)
  }
)

export interface ApiErrorDetail {
  status: number
  code: string
  message: string
  details?: any
}

export function parseApiError(error: unknown): ApiErrorDetail {
  if (axios.isAxiosError(error) && error.response) {
    const status = error.response.status
    const data = error.response.data as any

    if (data && data.error && typeof data.error === 'object' && data.error.code) {
      return {
        status,
        code: data.error.code,
        message: data.error.message || 'An error occurred',
        details: data.error.details,
      }
    }

    if (data && data.detail) {
      // Handle Sorty custom HTTPExceptions: detail = { code, message, details }
      if (typeof data.detail === 'object' && !Array.isArray(data.detail) && data.detail.code) {
        return {
          status,
          code: data.detail.code,
          message: data.detail.message || 'An error occurred',
          details: data.detail.details,
        }
      }
      
      // Handle FastAPI Pydantic validation errors: detail = [{ loc, msg, type }]
      if (Array.isArray(data.detail)) {
        return {
          status,
          code: 'validation_error',
          message: 'Invalid request parameters',
          details: data.detail,
        }
      }

      // Handle generic string details
      if (typeof data.detail === 'string') {
        return {
          status,
          code: 'error',
          message: data.detail,
        }
      }
    }

    return {
      status,
      code: 'unknown_error',
      message: error.message || 'An unknown error occurred',
      details: data,
    }
  }

  // Network error or non-Axios error
  return {
    status: 0,
    code: 'network_error',
    message: error instanceof Error ? error.message : 'Network error',
  }
}
