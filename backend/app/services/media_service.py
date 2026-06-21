import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MediaAsset, QualitySignal, ReviewDecision


@dataclass(frozen=True)
class MediaAssetCreate:
    event_id: uuid.UUID
    original_filename: str
    mime_type: str
    file_extension: str
    size_bytes: int
    sha256_hash: str | None = None
    batch_job_id: uuid.UUID | None = None


@dataclass(frozen=True)
class EventMediaSummaryData:
    event_id: uuid.UUID
    total_media: int
    processed_media: int
    needs_review_media: int
    failed_media: int
    blurry_media: int
    possible_duplicate_media: int
    pending_review_decisions: int
    approved_review_decisions: int
    edited_review_decisions: int
    rejected_review_decisions: int
    confirmed_duplicate_decisions: int
    export_ready_review_decisions: int


def build_original_object_key(
    event_id: uuid.UUID,
    media_id: uuid.UUID,
    file_extension: str,
) -> str:
    return f"events/{event_id}/originals/{media_id}{file_extension}"


def build_thumbnail_object_key(event_id: uuid.UUID, media_id: uuid.UUID) -> str:
    return f"events/{event_id}/thumbnails/{media_id}.jpg"


def create_media_asset(db: Session, payload: MediaAssetCreate) -> MediaAsset:
    settings = get_settings()
    media_id = uuid.uuid4()
    stored_filename = f"{media_id}{payload.file_extension}"
    original_object_key = build_original_object_key(
        payload.event_id,
        media_id,
        payload.file_extension,
    )
    thumbnail_object_key = build_thumbnail_object_key(payload.event_id, media_id)

    media = MediaAsset(
        id=media_id,
        event_id=payload.event_id,
        batch_job_id=payload.batch_job_id,
        original_filename=payload.original_filename,
        stored_filename=stored_filename,
        bucket_name=settings.minio_bucket,
        original_object_key=original_object_key,
        thumbnail_object_key=thumbnail_object_key,
        mime_type=payload.mime_type,
        file_extension=payload.file_extension,
        size_bytes=payload.size_bytes,
        sha256_hash=payload.sha256_hash,
        upload_status="accepted",
        processing_status="uploaded",
    )

    db.add(media)
    db.commit()
    db.refresh(media)

    return media


def attach_media_to_batch_job(
    db: Session,
    media_ids: list[uuid.UUID],
    batch_job_id: uuid.UUID,
) -> None:
    if not media_ids:
        return

    media_assets = list(db.scalars(select(MediaAsset).where(MediaAsset.id.in_(media_ids))))
    for media in media_assets:
        media.batch_job_id = batch_job_id
        media.processing_status = "queued"

    db.commit()


def mark_batch_media_processing(db: Session, batch_job_id: uuid.UUID) -> None:
    media_assets = list(
        db.scalars(select(MediaAsset).where(MediaAsset.batch_job_id == batch_job_id))
    )
    for media in media_assets:
        media.processing_status = "processing"

    db.commit()


def mark_media_processing(db: Session, media: MediaAsset) -> MediaAsset:
    media.processing_status = "processing"
    media.processing_error = None
    db.commit()
    db.refresh(media)
    return media


def mark_media_processed(
    db: Session,
    media: MediaAsset,
    commit: bool = True,
) -> MediaAsset:
    media.processing_status = "processed"
    media.processing_error = None
    if commit:
        db.commit()
        db.refresh(media)
    return media


def mark_media_needs_review(
    db: Session,
    media: MediaAsset,
    reason: str | None = None,
    commit: bool = True,
) -> MediaAsset:
    media.processing_status = "needs_review"
    media.processing_error = reason
    if commit:
        db.commit()
        db.refresh(media)
    return media


def mark_media_failed(
    db: Session,
    media: MediaAsset,
    error_message: str,
) -> MediaAsset:
    media.processing_status = "failed"
    media.processing_error = error_message
    db.commit()
    db.refresh(media)
    return media


def mark_batch_media_processed(db: Session, batch_job_id: uuid.UUID) -> None:
    media_assets = list(
        db.scalars(select(MediaAsset).where(MediaAsset.batch_job_id == batch_job_id))
    )
    for media in media_assets:
        media.processing_status = "processed"
        media.processing_error = None

    db.commit()


def mark_batch_media_failed(
    db: Session,
    batch_job_id: uuid.UUID,
    error_message: str,
) -> None:
    media_assets = list(
        db.scalars(select(MediaAsset).where(MediaAsset.batch_job_id == batch_job_id))
    )
    for media in media_assets:
        media.processing_status = "failed"
        media.processing_error = error_message

    db.commit()


def list_event_media(
    db: Session,
    event_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[MediaAsset]:
    return list(
        db.scalars(
            select(MediaAsset)
            .where(MediaAsset.event_id == event_id)
            .order_by(MediaAsset.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def list_public_event_media(
    db: Session,
    event_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[MediaAsset]:
    return list(
        db.scalars(
            _public_media_statement(event_id)
            .order_by(MediaAsset.created_at.desc(), MediaAsset.id.asc())
            .limit(limit)
            .offset(offset)
        )
    )


def count_public_event_media(db: Session, event_id: uuid.UUID) -> int:
    statement = (
        select(func.count())
        .select_from(MediaAsset)
        .join(MediaAsset.review_decision)
        .where(*_public_media_conditions(event_id))
    )
    return db.scalar(statement) or 0


def get_public_event_media(
    db: Session,
    event_id: uuid.UUID,
    media_id: uuid.UUID,
) -> MediaAsset | None:
    return db.scalar(
        _public_media_statement(event_id).where(MediaAsset.id == media_id)
    )


def list_batch_media(
    db: Session,
    batch_job_id: uuid.UUID,
    media_ids: list[uuid.UUID] | None = None,
) -> list[MediaAsset]:
    statement = select(MediaAsset).where(MediaAsset.batch_job_id == batch_job_id)
    if media_ids is not None:
        statement = statement.where(MediaAsset.id.in_(media_ids))

    return list(
        db.scalars(
            statement.order_by(MediaAsset.created_at.asc(), MediaAsset.id.asc())
        )
    )


def count_event_media(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(MediaAsset).where(MediaAsset.event_id == event_id)
    ) or 0


def get_event_media_summary(
    db: Session,
    event_id: uuid.UUID,
) -> EventMediaSummaryData:
    return EventMediaSummaryData(
        event_id=event_id,
        total_media=_count_event_media_where(db, event_id),
        processed_media=_count_event_media_where(
            db,
            event_id,
            MediaAsset.processing_status == "processed",
        ),
        needs_review_media=_count_event_media_where(
            db,
            event_id,
            MediaAsset.processing_status == "needs_review",
        ),
        failed_media=_count_event_media_where(
            db,
            event_id,
            MediaAsset.processing_status == "failed",
        ),
        blurry_media=_count_quality_signals_where(
            db,
            event_id,
            QualitySignal.quality_label == "blurry",
        ),
        possible_duplicate_media=_count_quality_signals_where(
            db,
            event_id,
            QualitySignal.is_duplicate.is_(True),
        ),
        pending_review_decisions=_count_review_decisions_where(
            db,
            event_id,
            ReviewDecision.status == "pending",
        ),
        approved_review_decisions=_count_review_decisions_where(
            db,
            event_id,
            ReviewDecision.status == "approved",
        ),
        edited_review_decisions=_count_review_decisions_where(
            db,
            event_id,
            ReviewDecision.status == "edited",
        ),
        rejected_review_decisions=_count_review_decisions_where(
            db,
            event_id,
            ReviewDecision.status == "rejected",
        ),
        confirmed_duplicate_decisions=_count_review_decisions_where(
            db,
            event_id,
            ReviewDecision.status == "duplicate",
        ),
        export_ready_review_decisions=_count_review_decisions_where(
            db,
            event_id,
            ReviewDecision.status.in_(("approved", "edited")),
            ReviewDecision.include_in_export.is_(True),
        ),
    )


def get_media_asset(db: Session, media_id: uuid.UUID) -> MediaAsset | None:
    return db.scalar(select(MediaAsset).where(MediaAsset.id == media_id))


def _public_media_statement(event_id: uuid.UUID):
    return (
        select(MediaAsset)
        .join(MediaAsset.review_decision)
        .outerjoin(MediaAsset.ai_analysis)
        .outerjoin(MediaAsset.quality_signal)
        .where(*_public_media_conditions(event_id))
    )


def _public_media_conditions(event_id: uuid.UUID):
    return (
        MediaAsset.event_id == event_id,
        MediaAsset.processing_status == "processed",
        MediaAsset.thumbnail_object_key.is_not(None),
        ReviewDecision.status.in_(("approved", "edited")),
        ReviewDecision.include_in_export.is_(True),
    )


def _count_event_media_where(db: Session, event_id: uuid.UUID, *conditions) -> int:
    statement = (
        select(func.count())
        .select_from(MediaAsset)
        .where(MediaAsset.event_id == event_id)
    )
    for condition in conditions:
        statement = statement.where(condition)

    return db.scalar(statement) or 0


def _count_quality_signals_where(db: Session, event_id: uuid.UUID, *conditions) -> int:
    statement = (
        select(func.count())
        .select_from(QualitySignal)
        .join(QualitySignal.media)
        .where(MediaAsset.event_id == event_id)
    )
    for condition in conditions:
        statement = statement.where(condition)

    return db.scalar(statement) or 0


def _count_review_decisions_where(db: Session, event_id: uuid.UUID, *conditions) -> int:
    statement = (
        select(func.count())
        .select_from(ReviewDecision)
        .join(ReviewDecision.media)
        .where(MediaAsset.event_id == event_id)
    )
    for condition in conditions:
        statement = statement.where(condition)

    return db.scalar(statement) or 0
