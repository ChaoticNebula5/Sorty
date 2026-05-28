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
    locked_decision = _lock_review_decision(db, decision) or decision
    batch_job_id = (
        getattr(locked_decision.media, "batch_job_id", None)
        if locked_decision.media is not None
        else None
    )
    locked_batch_jobs = _lock_batch_jobs(db, [batch_job_id] if batch_job_id else [])

    locked_decision.status = payload.status
    locked_decision.final_primary_folder = payload.final_primary_folder
    locked_decision.final_sub_folder = payload.final_sub_folder
    locked_decision.final_tags = payload.final_tags
    locked_decision.include_in_export = (
        payload.include_in_export
        if payload.include_in_export is not None
        else payload.status in {"approved", "edited"}
    )
    locked_decision.reviewer_note = payload.reviewer_note
    locked_decision.reviewed_at = datetime.now(UTC)

    if locked_decision.media is not None:
        if payload.status in {"approved", "edited"}:
            locked_decision.media.processing_status = "processed"
            locked_decision.media.processing_error = None
        else:
            locked_decision.media.processing_status = "excluded"

    _mark_complete_review_batches(db, locked_batch_jobs)

    db.commit()
    db.refresh(locked_decision)
    return locked_decision


def _lock_review_decision(
    db: Session,
    decision: ReviewDecision,
) -> ReviewDecision | None:
    decision_id = getattr(decision, "id", None)
    if decision_id is None:
        return None

    return db.scalar(
        select(ReviewDecision)
        .where(ReviewDecision.id == decision_id)
        .with_for_update(of=ReviewDecision)
    )


def _lock_batch_jobs(db: Session, batch_job_ids: list[uuid.UUID]) -> list[BatchJob]:
    if not batch_job_ids:
        return []

    return list(
        db.scalars(
            select(BatchJob)
            .where(BatchJob.id.in_(batch_job_ids))
            .with_for_update(of=BatchJob)
        )
    )


def _mark_complete_review_batches(
    db: Session,
    batch_jobs: list[BatchJob],
) -> None:
    for batch_job in batch_jobs:
        if (
            batch_job.status == "waiting_for_review"
            and count_pending_reviews_for_batch(db, batch_job.id) == 0
        ):
            batch_job.status = "reviewed"
            batch_job.needs_review_count = 0


def bulk_approve_pending_reviews(
    db: Session,
    event_id: uuid.UUID,
    media_ids: list[uuid.UUID],
    reviewer_note: str | None = None,
) -> list[ReviewDecision]:
    decisions = list(
        db.scalars(
            select(ReviewDecision)
            .join(ReviewDecision.media)
            .where(
                MediaAsset.event_id == event_id,
                MediaAsset.id.in_(media_ids),
                ReviewDecision.status == "pending",
            )
            .with_for_update(of=ReviewDecision)
        )
    )

    found_media_ids = {decision.media_id for decision in decisions}
    missing_media_ids = set(media_ids) - found_media_ids
    if missing_media_ids:
        raise ValueError("All media_ids must belong to pending review items for this event.")

    reviewed_at = datetime.now(UTC)
    touched_batch_job_ids: set[uuid.UUID] = set()
    for decision in decisions:
        analysis = getattr(decision.media, "ai_analysis", None)
        if decision.media.batch_job_id is not None:
            touched_batch_job_ids.add(decision.media.batch_job_id)

        if not getattr(analysis, "suggested_primary_folder", None):
            db.rollback()
            raise ValueError("Bulk approval requires AI suggested folder metadata.")

        decision.status = "approved"
        decision.final_primary_folder = getattr(
            analysis,
            "suggested_primary_folder",
            None,
        )
        decision.final_sub_folder = getattr(analysis, "suggested_sub_folder", None)
        decision.final_tags = list(getattr(analysis, "tags", []) or [])
        decision.include_in_export = True
        decision.reviewer_note = reviewer_note
        decision.reviewed_at = reviewed_at
        decision.media.processing_status = "processed"
        decision.media.processing_error = None

    locked_batch_jobs = _lock_batch_jobs(db, list(touched_batch_job_ids))
    _mark_complete_review_batches(db, locked_batch_jobs)

    db.commit()
    for decision in decisions:
        db.refresh(decision)

    return decisions


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
