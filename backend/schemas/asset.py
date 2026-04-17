"""
Asset request/response schemas.
See PRD sections 9.2 (Upload) and 9.3 (Assets API).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AssetMetadataResponse(BaseModel):
    """Response schema for enriched asset metadata."""

    caption: str | None = None
    tags: list[str] = Field(default_factory=list, validation_alias="tags_json")
    primary_category: str | None = None
    category_scores: dict[str, float] = Field(
        default_factory=dict, validation_alias="category_scores_json"
    )
    usefulness_score: int | None = None
    blur_score: float | None = None
    brightness_score: float | None = None
    sponsor_visible_score: float | None = None
    duplicate_hidden: bool = False
    low_quality_flag: bool = False

    model_config = {"from_attributes": True}


class AssetResponse(BaseModel):
    """Response schema for an asset object."""

    id: UUID
    filename: str
    url: str
    thumbnail_url: str
    width: int | None = None
    height: int | None = None
    file_size: int
    uploaded_at: datetime
    processing_status: str
    metadata: AssetMetadataResponse | None = Field(
        default=None, validation_alias="asset_metadata"
    )

    model_config = {"from_attributes": True}


class AssetListData(BaseModel):
    """Paginated asset list payload."""

    total_count: int
    limit: int
    offset: int
    assets: list[AssetResponse]


class AssetListResponse(BaseModel):
    """Response schema for paginated asset list."""

    data: AssetListData


class UploadAssetItem(BaseModel):
    """Uploaded asset item returned from upload response."""

    id: UUID
    filename: str
    processing_status: str


class UploadResponseData(BaseModel):
    """Upload response payload."""

    uploaded: int
    skipped_duplicates: int
    rejected_invalid: int
    assets: list[UploadAssetItem]


class UploadResponse(BaseModel):
    """Response schema for upload endpoint."""

    data: UploadResponseData


class ReprocessResponseData(BaseModel):
    """Reprocess response payload."""

    job_id: UUID
    status: str


class ReprocessResponse(BaseModel):
    """Response schema for asset reprocess endpoint."""

    data: ReprocessResponseData


class ClusterResponseData(BaseModel):
    """Manual clustering response payload."""

    status: str


class ClusterResponse(BaseModel):
    """Response schema for manual event clustering endpoint."""

    data: ClusterResponseData
