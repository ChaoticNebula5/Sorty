"""
Override request/response schemas.
See PRD section 9.8 (Overrides API).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class OverrideCreate(BaseModel):
    """Request schema for creating an override."""

    type: Literal[
        "hide",
        "pin",
        "tag_override",
        "caption_override",
        "sponsor_visible_override",
        "useful_override",
    ]
    value: str | None = None


class OverrideResponse(BaseModel):
    """Response schema for a created override."""

    id: UUID
    asset_id: UUID
    type: str
    value: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
