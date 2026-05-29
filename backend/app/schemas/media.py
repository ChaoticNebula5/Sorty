import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MediaQualityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    blur_score: float | None = None
    quality_label: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    is_duplicate: bool = False
    duplicate_distance: int | None = None
    duplicate_group_id: uuid.UUID | None = None
    exif_camera_make: str | None = None
    exif_camera_model: str | None = None


class MediaAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    batch_job_id: uuid.UUID | None
    original_filename: str
    stored_filename: str
    mime_type: str
    file_extension: str
    size_bytes: int
    upload_status: str
    processing_status: str
    processing_error: str | None = None
    quality: MediaQualityRead | None = None
    thumbnail_url: str | None = None
    file_url: str | None = None
    created_at: datetime
    updated_at: datetime


class BatchUploadRejectedItem(BaseModel):
    filename: str
    code: str
    message: str


class BatchUploadResponse(BaseModel):
    event_id: uuid.UUID
    job_id: uuid.UUID | None
    job_status: str | None
    accepted_count: int
    rejected_count: int
    media_ids: list[uuid.UUID]
    rejected_files: list[BatchUploadRejectedItem]
