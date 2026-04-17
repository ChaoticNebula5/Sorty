"""
Search request/response schemas.
See PRD section 9.4 (Search API).
"""

from typing import Literal

from pydantic import BaseModel, Field

from backend.schemas.asset import AssetResponse


class SearchFilters(BaseModel):
    """Search filter options."""

    categories: list[str] | None = None
    min_quality: int = Field(default=0, ge=0, le=100)
    exclude_duplicates: bool = True
    exclude_low_quality: bool = False


class SearchRequest(BaseModel):
    """Request schema for event search."""

    query: str = Field(..., min_length=1)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    sort: Literal["relevance", "date", "quality"] = Field(default="relevance")
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class SearchScore(BaseModel):
    """Per-result scoring breakdown."""

    total: float
    semantic_similarity: float
    keyword_match: float
    usefulness_score_normalized: float
    category_match: float


class SearchResultItem(BaseModel):
    """Single search result item."""

    asset: AssetResponse
    score: SearchScore


class SearchResponseData(BaseModel):
    """Paginated search response payload."""

    total_count: int
    limit: int
    offset: int
    results: list[SearchResultItem]


class SearchResponse(BaseModel):
    """Response schema for search endpoint."""

    data: SearchResponseData
