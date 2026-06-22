import { apiClient } from './client'
import type { APIResponse, ExportJob } from './types'

export interface ExportCreateRequest {
  include_duplicates?: boolean
  include_blurry?: boolean
  include_pending?: boolean
}

export async function createExport(eventId: string, payload: ExportCreateRequest): Promise<APIResponse<ExportJob>> {
  const { data } = await apiClient.post<APIResponse<ExportJob>>(`/events/${eventId}/export`, payload)
  return data
}

export async function getExportJob(exportId: string): Promise<APIResponse<ExportJob>> {
  const { data } = await apiClient.get<APIResponse<ExportJob>>(`/exports/${exportId}`)
  return data
}

export function getExportDownloadUrl(exportId: string): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
  return `${baseUrl}/exports/${exportId}/download`
}
