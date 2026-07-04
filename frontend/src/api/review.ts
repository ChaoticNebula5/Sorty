import { apiClient } from './client'
import type { APIListResponse, APIResponse, ReviewQueueItem, ReviewDecisionUpdate } from './types'

export async function getReviewQueue(eventId: string): Promise<APIListResponse<ReviewQueueItem>> {
  const { data } = await apiClient.get<APIListResponse<ReviewQueueItem>>(`/events/${eventId}/review-queue`)
  return data
}

export async function updateReviewDecision({ mediaId, payload }: { mediaId: string, payload: ReviewDecisionUpdate }): Promise<APIResponse<any>> {
  const { data } = await apiClient.patch<APIResponse<any>>(`/media/${mediaId}/review`, payload)
  return data
}
