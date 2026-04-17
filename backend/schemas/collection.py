"""
Collection request/response schemas.
See PRD section 9.5 (Collections API).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    """Request schema for creating a collection."""

    name: str = Field(..., min_length=1, max_length=255)


class CollectionResponse(BaseModel):
    """Response schema for a collection object."""

    id: UUID
    event_id: UUID
    name: str
    asset_count: int
    created_at: datetime


class CollectionListItem(BaseModel):
    """Response schema for collection list item."""

    id: UUID
    name: str
    asset_count: int
    created_at: datetime


class CollectionListResponse(BaseModel):
    """Response schema for listing collections."""

    data: list[CollectionListItem]


class AddCollectionAssetsRequest(BaseModel):
    """Request schema for adding assets to a collection."""

    asset_ids: list[UUID] = Field(..., min_length=1)


class AddCollectionAssetsResponseData(BaseModel):
    """Response payload for adding assets to a collection."""

    added: int
    already_present: int


class AddCollectionAssetsResponse(BaseModel):
    """Response schema for adding assets to a collection."""

    data: AddCollectionAssetsResponseData


class RemoveCollectionAssetResponseData(BaseModel):
    """Response payload for removing an asset from a collection."""

    removed: bool


class RemoveCollectionAssetResponse(BaseModel):
    """Response schema for removing an asset from a collection."""

    data: RemoveCollectionAssetResponseData
