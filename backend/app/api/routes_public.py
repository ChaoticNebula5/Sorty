import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.common import APIListResponse, APIResponse, Pagination
from app.schemas.events import PublicEventRead
from app.schemas.media import PublicMediaRead
from app.services import event_service, media_service, storage_factory

router = APIRouter(prefix="/api/public", tags=["public"])


def get_public_event_or_404(db: Session, public_slug: str):
    event = event_service.get_public_event_by_slug(db, public_slug)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "public_event_not_found",
                "message": "Public event not found.",
                "details": {"public_slug": public_slug},
            },
        )
    return event


def public_media_to_read(public_slug: str, media) -> PublicMediaRead:
    review = getattr(media, "review_decision", None)
    quality = getattr(media, "quality_signal", None)

    return PublicMediaRead(
        media_id=media.id,
        thumbnail_url=(
            f"/api/publ1ic/events/{public_slug}/media/{media.id}/thumbnail"
        ),
        caption=None,
        tags=list(getattr(review, "final_tags", []) or []),
        quality_label=getattr(quality, "quality_label", None),
    )


@router.get("/events/{public_slug}")
def get_public_event(
    public_slug: str,
    db: Session = Depends(get_db),
) -> APIResponse:
    event = get_public_event_or_404(db, public_slug)

    return APIResponse(
        data=PublicEventRead(
            name=event.name,
            event_type=event.event_type,
            description=event.description,
            event_date=event.event_date,
            public_slug=event.public_slug,
            published_at=event.published_at,
        ),
        error=None,
    )


@router.get("/events/{public_slug}/media")
def list_public_event_media(
    public_slug: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> APIListResponse:
    event = get_public_event_or_404(db, public_slug)
    media_items = media_service.list_public_event_media(
        db,
        event_id=event.id,
        limit=limit,
        offset=offset,
    )
    total = media_service.count_public_event_media(db, event.id)

    return APIListResponse(
        data=[public_media_to_read(public_slug, media) for media in media_items],
        pagination=Pagination(limit=limit, offset=offset, total=total),
        error=None,
    )


@router.get("/events/{public_slug}/media/{media_id}/thumbnail")
def get_public_media_thumbnail(
    public_slug: str,
    media_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    event = get_public_event_or_404(db, public_slug)
    media = media_service.get_public_event_media(db, event.id, media_id)
    if media is None or media.thumbnail_object_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "public_media_not_found",
                "message": "Public media not found.",
                "details": {"public_slug": public_slug},
            },
        )

    storage = storage_factory.get_storage_service()
    try:
        if not storage.object_exists(media.thumbnail_object_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "public_media_not_found",
                    "message": "Public media not found.",
                    "details": {"public_slug": public_slug},
                },
            )
        data = storage.get_bytes(media.thumbnail_object_key)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "storage_unavailable",
                "message": "Could not retrieve media from storage.",
                "details": {},
            },
        ) from exc

    return StreamingResponse(
        BytesIO(data),
        media_type="image/jpeg",
        headers={"Content-Disposition": f'inline; filename="{media.id}-thumbnail.jpg"'},
    )
