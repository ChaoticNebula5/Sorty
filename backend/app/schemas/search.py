import uuid

from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    media_id: uuid.UUID
    original_filename: str
    thumbnail_url: str
    file_url: str
    caption: str | None
    tags: list[str]
    primary_folder: str | None
    sub_folder: str | None
    review_status: str | None
    include_in_export: bool | None
    quality_label: str | None
    is_duplicate: bool
    score: float


class SearchQueryParams(BaseModel):
    q: str = Field(min_length=2, max_length=200)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    include_duplicates: bool = False
    include_blurry: bool = True
    include_pending: bool = False
    export_ready_only: bool = True
