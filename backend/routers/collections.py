"""
Collection API router.
Handles collection creation, listing, and membership changes.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.collection import AddCollectionAssetsRequest, CollectionCreate
from backend.services.collection_service import CollectionService


router = APIRouter(tags=["collections"])


@router.post("/events/{event_id}/collections", status_code=status.HTTP_201_CREATED)
async def create_collection(
    event_id: UUID,
    payload: CollectionCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a collection for an event."""
    service = CollectionService(db)
    result = await service.create_collection(event_id, payload)
    return {"data": result.model_dump(), "error": None}


@router.get("/events/{event_id}/collections")
async def list_collections(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List collections for an event."""
    service = CollectionService(db)
    result = await service.list_collections(event_id)
    return {"data": [item.model_dump() for item in result.data], "error": None}


@router.post("/collections/{collection_id}/assets")
async def add_collection_assets(
    collection_id: UUID,
    payload: AddCollectionAssetsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Add assets to a collection."""
    service = CollectionService(db)
    result = await service.add_assets(collection_id, payload)
    return {"data": result.data.model_dump(), "error": None}


@router.delete("/collections/{collection_id}/assets/{asset_id}")
async def remove_collection_asset(
    collection_id: UUID,
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove a single asset from a collection."""
    service = CollectionService(db)
    result = await service.remove_asset(collection_id, asset_id)
    return {"data": result.data.model_dump(), "error": None}
