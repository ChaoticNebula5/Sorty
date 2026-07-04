import { apiClient, parseApiError } from './client'
import type { APIResponse, BatchJob, BatchUploadResponse } from './types'

export async function uploadMediaBatch(
  eventId: string,
  files: File[],
  onProgress?: (percent: number) => void
): Promise<APIResponse<BatchUploadResponse>> {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })

  try {
    const { data } = await apiClient.post<APIResponse<BatchUploadResponse>>(
      `/events/${eventId}/media/batch-upload`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            onProgress?.(percentCompleted)
          }
        },
      }
    )
    return data
  } catch (error) {
    throw parseApiError(error)
  }
}

export async function getJobStatus(jobId: string): Promise<APIResponse<BatchJob>> {
  const { data } = await apiClient.get<APIResponse<BatchJob>>(`/jobs/${jobId}`)
  return data
}

export async function resumeJob(jobId: string) {
  const { data } = await apiClient.post<APIResponse<any>>(`/jobs/${jobId}/resume`)
  return data
}
