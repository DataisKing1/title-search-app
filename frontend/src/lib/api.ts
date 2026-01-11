import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '../store/auth'

const API_URL = import.meta.env.VITE_API_URL || '/api'

// API Error response type
interface ApiErrorResponse {
  detail?: string | { msg: string }[]
  message?: string
}

// Helper to extract error message from axios error
export function getErrorMessage(error: unknown, defaultMessage = 'An error occurred'): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>
    const data = axiosError.response?.data

    if (data?.detail) {
      if (typeof data.detail === 'string') {
        return data.detail
      }
      // Handle validation errors (array of {msg: string})
      if (Array.isArray(data.detail) && data.detail.length > 0) {
        return data.detail.map(d => d.msg).join(', ')
      }
    }

    if (data?.message) {
      return data.message
    }

    // Network errors
    if (axiosError.code === 'ERR_NETWORK') {
      return 'Network error. Please check your connection.'
    }

    if (axiosError.code === 'ECONNABORTED') {
      return 'Request timed out. Please try again.'
    }
  }

  if (error instanceof Error) {
    return error.message
  }

  return defaultMessage
}

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: async (email: string, password: string) => {
    const formData = new URLSearchParams()
    formData.append('username', email)
    formData.append('password', password)

    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    return response.data
  },

  register: async (email: string, password: string, fullName?: string) => {
    const response = await api.post('/auth/register', {
      email,
      password,
      full_name: fullName,
    })
    return response.data
  },

  getMe: async () => {
    const response = await api.get('/auth/me')
    return response.data
  },

  changePassword: async (oldPassword: string, newPassword: string) => {
    const response = await api.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
    return response.data
  },
}

// Searches API
export const searchesApi = {
  list: async (page = 1, pageSize = 20, status?: string, county?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (status) params.append('status_filter', status)
    if (county) params.append('county', county)

    const response = await api.get(`/searches?${params}`)
    return response.data
  },

  getStats: async () => {
    const response = await api.get('/searches/stats/dashboard')
    return response.data
  },

  get: async (id: number) => {
    const response = await api.get(`/searches/${id}`)
    return response.data
  },

  create: async (data: {
    street_address: string
    city: string
    county: string
    state?: string
    zip_code?: string
    parcel_number?: string
    search_type?: string
    search_years?: number
    priority?: string
  }) => {
    const response = await api.post('/searches', data)
    return response.data
  },

  getStatus: async (id: number) => {
    const response = await api.get(`/searches/${id}/status`)
    return response.data
  },

  cancel: async (id: number) => {
    const response = await api.post(`/searches/${id}/cancel`)
    return response.data
  },

  retry: async (id: number) => {
    const response = await api.post(`/searches/${id}/retry`)
    return response.data
  },

  runSync: async (id: number) => {
    const response = await api.post(`/searches/${id}/run-sync`)
    return response.data
  },

  delete: async (id: number) => {
    const response = await api.delete(`/searches/${id}`)
    return response.data
  },

  getDocuments: async (id: number) => {
    const response = await api.get(`/searches/${id}/documents`)
    return response.data
  },

  getChainOfTitle: async (id: number) => {
    const response = await api.get(`/searches/${id}/chain-of-title`)
    return response.data
  },

  getEncumbrances: async (id: number) => {
    const response = await api.get(`/searches/${id}/encumbrances`)
    return response.data
  },

  getChainAnalysis: async (id: number) => {
    const response = await api.get(`/searches/${id}/chain-analysis`)
    return response.data
  },
}

// Documents API
export const documentsApi = {
  get: async (id: number) => {
    const response = await api.get(`/documents/${id}`)
    return response.data
  },

  getOcr: async (id: number) => {
    const response = await api.get(`/documents/${id}/ocr`)
    return response.data
  },

  upload: async (searchId: number, file: File, documentType: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_type', documentType)

    const response = await api.post(`/documents/${searchId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
}

// Reports API
export const reportsApi = {
  list: async () => {
    const response = await api.get('/reports')
    return response.data
  },

  get: async (id: number) => {
    const response = await api.get(`/reports/${id}`)
    return response.data
  },

  exportJson: async (id: number) => {
    const response = await api.get(`/reports/${id}/export/json`)
    return response.data
  },

  approve: async (id: number) => {
    const response = await api.post(`/reports/${id}/approve`)
    return response.data
  },
}

// Batch API
export const batchApi = {
  upload: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await api.post('/batch/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  get: async (id: number) => {
    const response = await api.get(`/batch/${id}`)
    return response.data
  },

  process: async (id: number) => {
    const response = await api.post(`/batch/${id}/process`)
    return response.data
  },

  cancel: async (id: number) => {
    const response = await api.delete(`/batch/${id}`)
    return response.data
  },
}

// Counties API
export const countiesApi = {
  list: async (state = 'CO') => {
    const response = await api.get(`/counties?state=${state}`)
    return response.data
  },

  get: async (countyName: string) => {
    const response = await api.get(`/counties/${countyName}`)
    return response.data
  },

  getHealth: async (countyName: string) => {
    const response = await api.get(`/counties/${countyName}/health`)
    return response.data
  },
}

export default api
