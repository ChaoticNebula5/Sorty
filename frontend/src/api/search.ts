import { apiClient } from './client'
import type { APIListResponse, SearchResultItem } from './types'

export interface SearchParams {
  q?: string
  limit?: number
  offset?: number
  min_score?: number
  include_duplicates?: boolean
  include_blurry?: boolean
  include_pending?: boolean
  export_ready_only?: boolean
}

export async function searchEvent(eventId: string, params: SearchParams): Promise<APIListResponse<SearchResultItem>> {
  const { data } = await apiClient.get<APIListResponse<SearchResultItem>>(`/events/${eventId}/search`, {
    params
  })
  return data
}
