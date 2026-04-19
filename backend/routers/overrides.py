"""
Override API router.
Handles write-time override creation.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.override import OverrideCreate
from backend.services.override_service import OverrideService


router = APIRouter(tags=["overrides"])


@router.post("/assets/{asset_id}/overrides", status_code=status.HTTP_201_CREATED)
async def create_override(
    asset_id: UUID,
    payload: OverrideCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create an override for an asset."""
    service = OverrideService(db)
    try:
        result = await service.create_override(asset_id, payload)
    except ValueError as exc:
        message = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if message == "Asset not found"
            else status.HTTP_400_BAD_REQUEST
        )
        error_code = (
            "ASSET_NOT_FOUND"
            if status_code == status.HTTP_404_NOT_FOUND
            else "OVERRIDE_INVALID"
        )
        raise HTTPException(
            status_code=status_code,
            detail={"code": error_code, "message": message},
        ) from exc

    return {"data": result.model_dump(), "error": None}
