import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError


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
    is_public: bool = False
    public_slug: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class EventPublicSettingsUpdate(BaseModel):
    is_public: bool
    public_slug: str | None = Field(default=None, min_length=2, max_length=180)

    @field_validator("public_slug")
    @classmethod
    def validate_public_slug(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().lower()
        if not value:
            raise PydanticCustomError("blank_slug", "public_slug cannot be blank")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if any(character not in allowed for character in value):
            raise PydanticCustomError(
                "invalid_slug",
                "public_slug can contain only lowercase letters, numbers, and hyphens",
            )
        if value.startswith("-") or value.endswith("-") or "--" in value:
            raise PydanticCustomError("invalid_slug", "public_slug has invalid hyphens")
        return value


class PublicEventRead(BaseModel):
    name: str
    event_type: str | None
    description: str | None
    event_date: date | None
    public_slug: str
    published_at: datetime


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
