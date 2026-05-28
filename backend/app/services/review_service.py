import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import BatchJob, MediaAsset, ReviewDecision
from app.schemas.review import ReviewDecisionUpdate


def create_pending_review_decision(
    db: Session,
    media_id: uuid.UUID,
    review_reasons: list[str],
    commit: bool = True,
) -> ReviewDecision:
    decision = db.scalar(
        select(ReviewDecision).where(ReviewDecision.media_id == media_id)
    )
    if decision is None:
        decision = ReviewDecision(media_id=media_id)
        db.add(decision)

    decision.status = "pending"
    decision.include_in_export = False
    decision.review_reasons = review_reasons
    if commit:
        db.commit()
        db.refresh(decision)

    return decision


def list_event_review_queue(
    db: Session,
    event_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[ReviewDecision]:
    return list(
        db.scalars(
            select(ReviewDecision)
            .join(ReviewDecision.media)
            .where(
                MediaAsset.event_id == event_id,
                ReviewDecision.status == "pending",
            )
            .order_by(ReviewDecision.created_at.asc(), ReviewDecision.id.asc())
            .limit(limit)
            .offset(offset)
        )
    )


def count_event_review_queue(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ReviewDecision)
        .join(ReviewDecision.media)
        .where(
            MediaAsset.event_id == event_id,
            ReviewDecision.status == "pending",
        )
    ) or 0


def get_review_decision_for_media(
    db: Session,
    media_id: uuid.UUID,
) -> ReviewDecision | None:
    return db.scalar(select(ReviewDecision).where(ReviewDecision.media_id == media_id))


def apply_review_decision(
    db: Session,
    decision: ReviewDecision,
    payload: ReviewDecisionUpdate,
) -> ReviewDecision:
    decision.status = payload.status
    decision.final_primary_folder = payload.final_primary_folder
    decision.final_sub_folder = payload.final_sub_folder
    decision.final_tags = payload.final_tags
    decision.include_in_export = (
        payload.include_in_export
        if payload.include_in_export is not None
        else payload.status in {"approved", "edited"}
    )
    decision.reviewer_note = payload.reviewer_note
    decision.reviewed_at = datetime.now(UTC)

    if decision.media is not None:
        if payload.status in {"approved", "edited"}:
            decision.media.processing_status = "processed"
            decision.media.processing_error = None
        else:
            decision.media.processing_status = "excluded"

    db.commit()
    db.refresh(decision)
    return decision


def count_pending_reviews_for_batch(db: Session, batch_job_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ReviewDecision)
        .join(ReviewDecision.media)
        .where(
            MediaAsset.batch_job_id == batch_job_id,
            ReviewDecision.status == "pending",
        )
    ) or 0


def count_invalid_resolved_reviews_for_batch(db: Session, batch_job_id: uuid.UUID) -> int:
    decisions = list(
        db.scalars(
            select(ReviewDecision)
            .join(ReviewDecision.media)
            .where(
                MediaAsset.batch_job_id == batch_job_id,
                ReviewDecision.status != "pending",
            )
        )
    )

    invalid_count = 0
    for decision in decisions:
        if decision.status in {"approved", "edited"} and not decision.final_primary_folder:
            invalid_count += 1
        if decision.status in {"rejected", "duplicate"} and decision.include_in_export:
            invalid_count += 1
        if decision.status in {"rejected", "duplicate"} and (
            decision.final_primary_folder
            or decision.final_sub_folder
            or decision.final_tags
        ):
            invalid_count += 1

    return invalid_count


def get_review_batch_job(db: Session, decision: ReviewDecision) -> BatchJob | None:
    media = decision.media
    if media is None or media.batch_job_id is None:
        return None
    return db.scalar(select(BatchJob).where(BatchJob.id == media.batch_job_id))
