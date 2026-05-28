import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BatchJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    current_rq_job_id: str | None
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    needs_review_count: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class JobResumeResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    rq_job_id: str
    thread_id: str
    message: str
