import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin_auth
from app.schemas.common import APIListResponse, APIResponse, Pagination
from app.schemas.review import (
    BulkApproveReviewRequest,
    BulkApproveReviewResponse,
    ReviewDecisionRead,
    ReviewDecisionUpdate,
    ReviewQueueItem,
)
from app.services import event_service, media_service, review_service

router = APIRouter(
    prefix="/api",
    tags=["review"],
    dependencies=[Depends(require_admin_auth)],
)


def review_queue_item_to_read(decision) -> ReviewQueueItem:
    media = decision.media
    analysis = getattr(media, "ai_analysis", None)
    quality = getattr(media, "quality_signal", None)

    return ReviewQueueItem(
        media_id=media.id,
        thumbnail_url=f"/api/media/{media.id}/thumbnail",
        caption=getattr(analysis, "caption", None),
        tags=getattr(analysis, "tags", []) or [],
        suggested_primary_folder=getattr(analysis, "suggested_primary_folder", None),
        suggested_sub_folder=getattr(analysis, "suggested_sub_folder", None),
        quality_label=getattr(quality, "quality_label", None),
        is_duplicate=getattr(quality, "is_duplicate", False) if quality else False,
        duplicate_group_id=getattr(quality, "duplicate_group_id", None),
        review_reasons=decision.review_reasons,
        current_review_status=decision.status,
    )


def review_decision_to_read(decision) -> ReviewDecisionRead:
    return ReviewDecisionRead(
        media_id=decision.media_id,
        status=decision.status,
        final_primary_folder=decision.final_primary_folder,
        final_sub_folder=decision.final_sub_folder,
        final_tags=decision.final_tags,
        include_in_export=decision.include_in_export,
        review_reasons=decision.review_reasons,
        reviewer_note=decision.reviewer_note,
    )


@router.get("/events/{event_id}/review-queue")
def get_event_review_queue(
    event_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
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

    items = review_service.list_event_review_queue(
        db,
        event_id=event_id,
        limit=limit,
        offset=offset,
    )
    total = review_service.count_event_review_queue(db, event_id)

    return APIListResponse(
        data=[review_queue_item_to_read(item) for item in items],
        pagination=Pagination(limit=limit, offset=offset, total=total),
        error=None,
    )


@router.patch("/media/{media_id}/review")
def update_media_review(
    media_id: uuid.UUID,
    payload: ReviewDecisionUpdate,
    db: Session = Depends(get_db),
) -> APIResponse:
    media = media_service.get_media_asset(db, media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "media_not_found",
                "message": "Media asset not found.",
                "details": {"media_id": str(media_id)},
            },
        )

    decision = review_service.get_review_decision_for_media(db, media_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "review_decision_not_found",
                "message": "Review decision not found.",
                "details": {"media_id": str(media_id)},
            },
        )

    updated = review_service.apply_review_decision(db, decision, payload)
    return APIResponse(data=review_decision_to_read(updated), error=None)


@router.post("/events/{event_id}/review/bulk-approve")
def bulk_approve_event_reviews(
    event_id: uuid.UUID,
    payload: BulkApproveReviewRequest,
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

    try:
        decisions = review_service.bulk_approve_pending_reviews(
            db,
            event_id=event_id,
            media_ids=payload.media_ids,
            reviewer_note=payload.reviewer_note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "bulk_approve_invalid_items",
                "message": str(exc),
                "details": {
                    "event_id": str(event_id),
                    "media_ids": [str(media_id) for media_id in payload.media_ids],
                },
            },
        ) from exc

    return APIResponse(
        data=BulkApproveReviewResponse(
            event_id=event_id,
            approved_count=len(decisions),
            media_ids=[decision.media_id for decision in decisions],
        ),
        error=None,
    )
