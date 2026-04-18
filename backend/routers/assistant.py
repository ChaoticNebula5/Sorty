"""
Assistant API router.
Handles bounded assistant actions.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.assistant import AssistantActionRequest
from backend.services.assistant_service import AssistantService


router = APIRouter(tags=["assistant"])


@router.post("/events/{event_id}/assistant/action")
async def run_assistant_action(
    event_id: UUID,
    payload: AssistantActionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run a bounded assistant action for an event."""
    service = AssistantService(db)

    try:
        result = await service.run_action(event_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "ASSISTANT_ACTION_INVALID", "message": str(exc)},
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EVENT_NOT_FOUND", "message": "Event not found"},
        )

    return {"data": result.data.model_dump(), "error": None}
