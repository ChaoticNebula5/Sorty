import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EventCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    event_type: str | None = Field(default=None, max_length=80)
    description: str | None = None
    event_date: date | None = None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    event_type: str | None
    description: str | None
    event_date: date | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class EventMediaSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    total_media: int
    processed_media: int
    needs_review_media: int
    failed_media: int
    blurry_media: int
    possible_duplicate_media: int
    pending_review_decisions: int
    approved_review_decisions: int
    edited_review_decisions: int
    rejected_review_decisions: int
    confirmed_duplicate_decisions: int
    export_ready_review_decisions: int
