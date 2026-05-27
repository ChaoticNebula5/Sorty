import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    accepted_count: int
    rejected_count: int
    media_ids: list[uuid.UUID]
    rejected_files: list[BatchUploadRejectedItem]
