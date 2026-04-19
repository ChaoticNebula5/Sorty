"""
Upload API router.
Handles image uploads for events.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.upload_service import UploadService


router = APIRouter(tags=["upload"])


@router.post("/events/{event_id}/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_assets(
    event_id: UUID,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Upload one or more image assets for an event."""
    service = UploadService(db)

    try:
        result = await service.upload_assets(event_id, files)
    except ValueError as exc:
        message = str(exc)
        if message == "Event not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "EVENT_NOT_FOUND", "message": message},
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UPLOAD_INVALID", "message": message},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "UPLOAD_QUEUE_UNAVAILABLE", "message": str(exc)},
        ) from exc

    return {"data": result, "error": None}
