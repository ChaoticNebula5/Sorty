import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin_auth
from app.schemas.common import APIListResponse, Pagination
from app.schemas.search import SearchResultItem
from app.services import event_service, search_service

router = APIRouter(
    prefix="/api",
    tags=["search"],
    dependencies=[Depends(require_admin_auth)],
)


def search_result_to_read(result: search_service.SearchResult) -> SearchResultItem:
    media = result.media
    analysis = getattr(media, "ai_analysis", None)
    review = getattr(media, "review_decision", None)
    quality = getattr(media, "quality_signal", None)

    return SearchResultItem(
        media_id=media.id,
        original_filename=media.original_filename,
        thumbnail_url=f"/api/media/{media.id}/thumbnail",
        file_url=f"/api/media/{media.id}/file",
        caption=getattr(analysis, "caption", None),
        tags=list(getattr(review, "final_tags", []) or getattr(analysis, "tags", []) or []),
        primary_folder=getattr(review, "final_primary_folder", None)
        or getattr(analysis, "suggested_primary_folder", None),
        sub_folder=getattr(review, "final_sub_folder", None)
        or getattr(analysis, "suggested_sub_folder", None),
        review_status=getattr(review, "status", None),
        include_in_export=getattr(review, "include_in_export", None),
        quality_label=getattr(quality, "quality_label", None),
        is_duplicate=getattr(quality, "is_duplicate", False) if quality else False,
        score=result.score,
    )


@router.get("/events/{event_id}/search")
def search_event_media(
    event_id: uuid.UUID,
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    include_duplicates: bool = Query(default=False),
    include_blurry: bool = Query(default=True),
    include_pending: bool = Query(default=False),
    export_ready_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> APIListResponse:
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

    filters = search_service.SearchFilters(
        include_duplicates=include_duplicates,
        include_blurry=include_blurry,
        include_pending=include_pending,
        export_ready_only=export_ready_only,
    )
    results = search_service.search_event_media(
        db,
        event_id=event_id,
        query=q,
        limit=limit,
        offset=offset,
        filters=filters,
    )
    total = search_service.count_searchable_event_media(db, event_id, filters=filters)

    return APIListResponse(
        data=[search_result_to_read(result) for result in results],
        pagination=Pagination(limit=limit, offset=offset, total=total),
        error=None,
    )
