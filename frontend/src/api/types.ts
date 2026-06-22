export interface Pagination {
  limit: number
  offset: number
  total: number
}

export interface APIResponse<T> {
  data: T
  error: any | null
}

export interface APIListResponse<T> {
  data: T[]
  pagination: Pagination
  error: any | null
}

export type EventStatus =
  | 'processed'
  | 'review'
  | 'uploading'
  | 'needs-review'
  | 'archived'

export interface EventItem {
  id: string
  name: string
  event_type: string
  description?: string
  status?: string // Computed or basic status from backend
  is_public?: boolean
  public_slug?: string | null
  published_at?: string | null
  event_date?: string | null
  created_at: string
  updated_at: string
}

export interface PublicEvent {
  name: string
  event_type: string
  description?: string
  event_date?: string | null
  public_slug: string
  published_at: string
}

export interface PublicMediaItem {
  media_id: string
  thumbnail_url: string
  file_url?: string
  quality_label: string | null
  tags: string[]
}

export interface EventMediaSummary {
  event_id: string
  total_files: number
  total_size_bytes: number
  processing_status_counts: Record<string, number>
  quality_label_counts: Record<string, number>
}

export interface BatchJob {
  id: string
  event_id: string
  current_rq_job_id: string | null
  status: 'queued' | 'processing' | 'waiting_for_review' | 'reviewed' | 'completed' | 'partial_failed' | 'failed'
  total_files: number
  processed_files: number
  failed_files: number
  needs_review_count: number
  started_at: string | null
  completed_at: string | null
  error_message: string | null
}

export interface ReviewQueueItem {
  media_id: string
  thumbnail_url: string
  caption: string | null
  tags: string[]
  suggested_primary_folder: string | null
  suggested_sub_folder: string | null
  quality_label: string | null
  is_duplicate: boolean
  duplicate_group_id: string | null
  review_reasons: string[]
  current_review_status: string
}

export interface ReviewDecisionUpdate {
  status: 'approved' | 'edited' | 'rejected' | 'duplicate'
  final_primary_folder?: string | null
  final_sub_folder?: string | null
  final_tags: string[]
  include_in_export?: boolean | null
  reviewer_note?: string | null
}

export interface SearchResultItem {
  media_id: string
  original_filename: string
  thumbnail_url: string
  file_url: string
  caption: string | null
  tags: string[]
  primary_folder: string | null
  sub_folder: string | null
  review_status: string | null
  include_in_export: boolean | null
  quality_label: string | null
  is_duplicate: boolean
  score: number
}

export interface ExportJob {
  id: string
  event_id: string
  status: string
  export_type: string
  included_count: number
  excluded_count: number
  include_duplicates: boolean
  include_blurry: boolean
  include_pending: boolean
  download_url: string | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}
