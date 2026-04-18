"""
Event API router.
Handles event creation, listing, retrieval, and updates.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.event import EventCreate, EventUpdate
from backend.services.event_service import EventService


router = APIRouter(prefix="/events", tags=["events"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new event."""
    service = EventService(db)
    event = await service.create_event(payload)
    return {"data": event.model_dump(), "error": None}


@router.get("")
async def list_events(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all events with summary counts."""
    service = EventService(db)
    events = await service.list_events()
    return {"data": [event.model_dump() for event in events], "error": None}


@router.get("/{event_id}")
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a single event with aggregate stats."""
    service = EventService(db)
    event = await service.get_event(event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EVENT_NOT_FOUND", "message": "Event not found"},
        )

    return {"data": event.model_dump(), "error": None}


@router.patch("/{event_id}")
async def update_event(
    event_id: UUID,
    payload: EventUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update an existing event."""
    service = EventService(db)
    event = await service.update_event(event_id, payload)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EVENT_NOT_FOUND", "message": "Event not found"},
        )

    return {"data": event.model_dump(), "error": None}
