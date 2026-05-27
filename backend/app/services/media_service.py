import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MediaAsset


@dataclass(frozen=True)
class MediaAssetCreate:
    event_id: uuid.UUID
    original_filename: str
    mime_type: str
    file_extension: str
    size_bytes: int
    sha256_hash: str | None = None
    batch_job_id: uuid.UUID | None = None


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


def count_event_media(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(MediaAsset).where(MediaAsset.event_id == event_id)
    ) or 0


def get_media_asset(db: Session, media_id: uuid.UUID) -> MediaAsset | None:
    return db.scalar(select(MediaAsset).where(MediaAsset.id == media_id))
