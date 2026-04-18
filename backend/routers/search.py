"""
Search API router.
Handles event asset search.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.search import SearchRequest
from backend.services.retrieval_service import RetrievalService


router = APIRouter(tags=["search"])


@router.post("/events/{event_id}/search")
async def search_assets(
    event_id: UUID,
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Search assets for an event."""
    service = RetrievalService(db)
    result = await service.search_assets(event_id, payload)
    return {"data": result.data.model_dump(), "error": None}
