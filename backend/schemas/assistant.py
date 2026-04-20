"""
Assistant request/response schemas.
See PRD section 9.7 (Assistant API).
"""

from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field

from backend.models import AssistantAction


class AssistantActionParams(BaseModel):
    """Parameters for assistant actions."""

    count: int | None = Field(default=None, ge=1)
    prefer_categories: list[str] | None = None
    min_quality: int | None = Field(default=None, ge=0, le=100)


class AssistantActionRequest(BaseModel):
    """Request schema for assistant action endpoint."""

    action_type: AssistantAction
    params: AssistantActionParams = Field(default_factory=AssistantActionParams)


class AssistantActionResult(BaseModel):
    """Response payload for assistant action result."""

    collection_id: UUID | None = None
    collection_name: str | None = None
    asset_count: int | None = None
    summary: str | None = None
    extra: dict[str, Any] | None = None


class AssistantActionResponseData(BaseModel):
    """Response envelope data for assistant action endpoint."""

    run_id: UUID
    action_type: AssistantAction
    result: AssistantActionResult


class AssistantActionResponse(BaseModel):
    """Response schema for assistant action endpoint."""

    data: AssistantActionResponseData
