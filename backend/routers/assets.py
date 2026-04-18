"""
Asset API router.
Handles asset listing, reprocessing, and manual clustering.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.processing_service import ProcessingService
from backend.services.retrieval_service import RetrievalService


router = APIRouter(tags=["assets"])


@router.get("/events/{event_id}/assets")
async def list_assets(
    event_id: UUID,
    view: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="date"),
    order: str = Query(default="desc"),
    exclude_duplicates: bool = Query(default=True),
    exclude_low_quality: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List assets for an event with smart-view filters."""
    service = RetrievalService(db)
    result = await service.list_assets(
        event_id=event_id,
        view=view,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
        exclude_duplicates=exclude_duplicates,
        exclude_low_quality=exclude_low_quality,
    )
    return {"data": result.data.model_dump(), "error": None}


@router.post("/assets/{asset_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Requeue an asset for metadata enrichment."""
    service = ProcessingService(db)
    result = await service.reprocess_asset(asset_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ASSET_NOT_FOUND", "message": "Asset not found"},
        )

    return {"data": result.data.model_dump(), "error": None}


@router.post("/events/{event_id}/cluster", status_code=status.HTTP_202_ACCEPTED)
async def cluster_event(
    event_id: UUID,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Manually enqueue duplicate clustering for an event."""
    service = ProcessingService(db)
    result = await service.enqueue_event_clustering(event_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EVENT_NOT_FOUND", "message": "Event not found"},
        )

    response.status_code = (
        status.HTTP_200_OK
        if result.data.status == "already_running"
        else status.HTTP_202_ACCEPTED
    )

    return {"data": result.data.model_dump(), "error": None}
