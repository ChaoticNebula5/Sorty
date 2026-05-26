import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.schemas.common import APIListResponse, APIResponse, Pagination
from app.schemas.events import EventCreate, EventRead
from app.services import event_service

router = APIRouter(
    prefix="/api/events",
    tags=["events"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
) -> APIResponse:
    event = event_service.create_event(db, payload)

    return APIResponse(
        data=EventRead.model_validate(event),
        error=None,
    )


@router.get("")
def list_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> APIListResponse:
    events, total = event_service.list_events(db, limit=limit, offset=offset)

    return APIListResponse(
        data=[EventRead.model_validate(event) for event in events],
        pagination=Pagination(limit=limit, offset=offset, total=total),
        error=None,
    )


@router.get("/{event_id}")
def get_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> APIResponse:
    event = event_service.get_event(db, event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "event_not_found",
                "message": "Event not found.",
                "details": {"event_id": str(event_id)},
            },
        )

    return APIResponse(
        data=EventRead.model_validate(event),
        error=None,
    )
