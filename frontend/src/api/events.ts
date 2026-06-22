import { apiClient } from './client'
import type { APIListResponse, APIResponse, EventItem, EventMediaSummary, BatchJob, PublicEvent, PublicMediaItem } from './types'

export async function getEvents(): Promise<APIListResponse<EventItem>> {
  const { data } = await apiClient.get<APIListResponse<EventItem>>('/events')
  return data
}

export async function createEvent(payload: { name: string; event_type: string; description?: string }): Promise<APIResponse<EventItem>> {
  const { data } = await apiClient.post<APIResponse<EventItem>>('/events', payload)
  return data
}

export async function getEvent(eventId: string): Promise<APIResponse<EventItem>> {
  const { data } = await apiClient.get<APIResponse<EventItem>>(`/events/${eventId}`)
  return data
}

export async function getEventSummary(eventId: string): Promise<APIResponse<EventMediaSummary>> {
  const { data } = await apiClient.get<APIResponse<EventMediaSummary>>(`/events/${eventId}/media-summary`)
  return data
}

export async function getEventJobs(eventId: string): Promise<APIListResponse<BatchJob>> {
  const { data } = await apiClient.get<APIListResponse<BatchJob>>(`/events/${eventId}/jobs`)
  return data
}

export async function updateEventPublicSettings(
  eventId: string,
  payload: { is_public: boolean; public_slug?: string | null }
): Promise<APIResponse<EventItem>> {
  const { data } = await apiClient.patch<APIResponse<EventItem>>(`/events/${eventId}/public`, payload)
  return data
}

export async function getPublicEvent(publicSlug: string): Promise<APIResponse<PublicEvent>> {
  const { data } = await apiClient.get<APIResponse<PublicEvent>>(`/public/events/${publicSlug}`)
  return data
}

export async function getPublicEventMedia(
  publicSlug: string,
  limit: number = 50,
  offset: number = 0
): Promise<APIListResponse<PublicMediaItem>> {
  const { data } = await apiClient.get<APIListResponse<PublicMediaItem>>(`/public/events/${publicSlug}/media`, {
    params: { limit, offset }
  })
  return data
}
