import axios from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
    // In a real app we'd get this from a store or context
    'X-API-Key': 'demo-secret',
  },
})

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
