"""
Event request/response schemas.
See PRD section 9.1 (Events API).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    """Request schema for creating an event."""

    name: str = Field(..., min_length=1, max_length=255, description="Event name")


class EventUpdate(BaseModel):
    """Request schema for updating an event."""

    name: str = Field(..., min_length=1, max_length=255, description="Event name")


class EventStats(BaseModel):
    """Event statistics."""

    total_assets: int = Field(..., description="Total number of assets")
    processed: int = Field(..., description="Successfully processed assets")
    failed: int = Field(..., description="Failed processing assets")
    pending: int = Field(..., description="Pending processing assets")
    processing: int = Field(..., description="Currently processing assets")
    duplicate_clusters: int = Field(..., description="Number of duplicate clusters")
    low_quality_count: int = Field(..., description="Number of low quality assets")


class EventResponse(BaseModel):
    """Response schema for an event object."""

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventWithStats(EventResponse):
    """Response schema for an event with statistics."""

    stats: EventStats


class EventListItem(BaseModel):
    """Response schema for an event list item."""

    id: UUID
    name: str
    asset_count: int
    processed_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    """Response schema for a list of events."""

    data: list[EventListItem]
