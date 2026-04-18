"""
Export API router.
Handles export creation and status polling.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.export_service import ExportService


router = APIRouter(tags=["export"])


@router.post(
    "/collections/{collection_id}/export", status_code=status.HTTP_202_ACCEPTED
)
async def create_export(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create an export job for a collection."""
    service = ExportService(db)

    try:
        result = await service.create_export(collection_id)
    except ValueError as exc:
        message = str(exc)
        if message == "Collection not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "COLLECTION_NOT_FOUND", "message": message},
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "EXPORT_TOO_LARGE", "message": message},
        ) from exc

    return {"data": result.data.model_dump(), "error": None}


@router.get("/exports/{export_id}")
async def get_export_status(
    export_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get export status for polling."""
    service = ExportService(db)
    result = await service.get_export_status(export_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EXPORT_NOT_FOUND", "message": "Export not found"},
        )

    return {"data": result.data.model_dump(), "error": None}
