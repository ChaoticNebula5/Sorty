import { apiClient } from './client'
import type { APIResponse, ExportJob } from './types'
import { resolveApiUrl } from './client'

export interface ExportCreateRequest {
  include_duplicates?: boolean
  include_blurry?: boolean
  include_pending?: boolean
}

export interface ExportDownload {
  blob: Blob
  filename: string
}

export async function createExport(eventId: string, payload: ExportCreateRequest): Promise<APIResponse<ExportJob>> {
  const { data } = await apiClient.post<APIResponse<ExportJob>>(`/events/${eventId}/export`, payload)
  return data
}

export async function getExportJob(exportId: string): Promise<APIResponse<ExportJob>> {
  const { data } = await apiClient.get<APIResponse<ExportJob>>(`/exports/${exportId}`)
  return data
}

export async function downloadExportZip(exportId: string): Promise<ExportDownload> {
  const response = await apiClient.get<Blob>(`/exports/${exportId}/download`, {
    headers: {
      Accept: 'application/zip',
    },
    responseType: 'blob',
  })
  const contentType = response.headers['content-type']
  if (typeof contentType === 'string' && contentType.includes('application/json')) {
    const body = await response.data.text()
    throw new Error(body || 'Export download returned JSON instead of a ZIP archive.')
  }
  if (response.data.size === 0) {
    throw new Error('Export download returned an empty ZIP archive.')
  }

  const contentDisposition = response.headers['content-disposition']
  const filenameMatch = typeof contentDisposition === 'string'
    ? contentDisposition.match(/filename="?([^";]+)"?/i)
    : null

  return {
    blob: response.data,
    filename: filenameMatch?.[1]?.trim() || `${exportId}.zip`,
  }
}

export function getExportDownloadUrl(exportJob: ExportJob): string | null {
  return exportJob.download_url ? resolveApiUrl(exportJob.download_url) : null
}
