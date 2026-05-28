import csv
import re
import uuid
import zipfile
from datetime import UTC, datetime
from io import BytesIO, StringIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.models import Event, ExportJob, MediaAsset, ReviewDecision
from app.schemas.export import ExportCreateRequest
from app.services.storage_service import StorageService


class ExportBlockedError(ValueError):
    pass


def build_export_object_key(event_id: uuid.UUID, export_id: uuid.UUID) -> str:
    return f"events/{event_id}/exports/{export_id}.zip"


def sanitize_zip_segment(value: str | None, fallback: str) -> str:
    candidate = (value or fallback).strip()
    candidate = re.sub(r"[\\/:*?\"<>|]+", "_", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" .")
    return candidate[:80] or fallback


def get_export_job(db: Session, export_id: uuid.UUID) -> ExportJob | None:
    return db.scalar(select(ExportJob).where(ExportJob.id == export_id))


def count_pending_reviews(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ReviewDecision)
        .join(ReviewDecision.media)
        .where(
            MediaAsset.event_id == event_id,
            ReviewDecision.status == "pending",
        )
    ) or 0


def count_event_media(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(MediaAsset).where(MediaAsset.event_id == event_id)
    ) or 0


def list_export_candidates(
    db: Session,
    event_id: uuid.UUID,
    payload: ExportCreateRequest,
) -> list[MediaAsset]:
    media_items = list(
        db.scalars(
            select(MediaAsset)
            .where(MediaAsset.event_id == event_id)
            .options(
                selectinload(MediaAsset.ai_analysis),
                selectinload(MediaAsset.quality_signal),
                selectinload(MediaAsset.review_decision),
            )
            .order_by(MediaAsset.created_at.asc(), MediaAsset.id.asc())
        )
    )

    exportable: list[MediaAsset] = []
    for media in media_items:
        if should_include_media_in_export(media, payload):
            exportable.append(media)

    return exportable


def should_include_media_in_export(
    media: MediaAsset,
    payload: ExportCreateRequest,
) -> bool:
    review = media.review_decision
    quality = media.quality_signal

    if getattr(quality, "quality_label", None) == "blurry" and not payload.include_blurry:
        return False

    if review is None or review.status == "pending":
        return payload.include_pending

    if review.status == "rejected":
        return False

    if review.status == "duplicate":
        return payload.include_duplicates

    return review.status in {"approved", "edited"} and review.include_in_export


def build_export_zip_bytes(
    event: Event,
    media_items: list[MediaAsset],
    storage: StorageService,
) -> bytes:
    buffer = BytesIO()
    metadata_rows: list[dict[str, str]] = []

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, media in enumerate(media_items, start=1):
            review = media.review_decision
            analysis = media.ai_analysis

            primary_folder = sanitize_zip_segment(
                getattr(review, "final_primary_folder", None)
                or getattr(analysis, "suggested_primary_folder", None),
                "Unsorted",
            )
            sub_folder = sanitize_zip_segment(
                getattr(review, "final_sub_folder", None)
                or getattr(analysis, "suggested_sub_folder", None),
                "General",
            )
            filename = sanitize_zip_segment(media.original_filename, f"media-{index}")
            archive_path = f"{primary_folder}/{sub_folder}/{index:04d}-{filename}"

            archive.writestr(archive_path, storage.get_bytes(media.original_object_key))
            metadata_rows.append(
                {
                    "media_id": str(media.id),
                    "original_filename": media.original_filename,
                    "archive_path": archive_path,
                    "review_status": getattr(review, "status", "") or "",
                    "caption": getattr(analysis, "caption", "") or "",
                    "tags": ", ".join(getattr(review, "final_tags", []) or getattr(analysis, "tags", []) or []),
                }
            )

        archive.writestr("metadata.csv", build_metadata_csv(metadata_rows))
        archive.writestr(
            "summary.md",
            build_summary_markdown(event=event, included_count=len(media_items)),
        )

    return buffer.getvalue()


def build_metadata_csv(rows: list[dict[str, str]]) -> str:
    output = StringIO()
    fieldnames = [
        "media_id",
        "original_filename",
        "archive_path",
        "review_status",
        "caption",
        "tags",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def build_summary_markdown(event: Event, included_count: int) -> str:
    return "\n".join(
        [
            f"# {event.name}",
            "",
            f"Included media: {included_count}",
            f"Generated at: {datetime.now(UTC).isoformat()}",
            "",
        ]
    )


def create_and_generate_export(
    db: Session,
    event: Event,
    payload: ExportCreateRequest,
    storage: StorageService,
) -> ExportJob:
    if not payload.include_pending and count_pending_reviews(db, event.id) > 0:
        raise ExportBlockedError("Export is blocked while review items are pending.")

    export_id = uuid.uuid4()
    export_job = ExportJob(
        id=export_id,
        event_id=event.id,
        status="exporting",
        export_type="organized_zip",
        bucket_name=get_settings().minio_bucket,
        zip_object_key=build_export_object_key(event.id, export_id),
        include_duplicates=payload.include_duplicates,
        include_blurry=payload.include_blurry,
        include_pending=payload.include_pending,
    )
    db.add(export_job)
    db.commit()
    db.refresh(export_job)

    try:
        media_items = list_export_candidates(db, event.id, payload)
        zip_bytes = build_export_zip_bytes(event, media_items, storage)
        storage.put_bytes(
            export_job.zip_object_key,
            zip_bytes,
            content_type="application/zip",
        )
        export_job.status = "completed"
        export_job.included_count = len(media_items)
        export_job.excluded_count = max(
            0,
            count_event_media(db, event.id) - len(media_items),
        )
        export_job.completed_at = datetime.now(UTC)
        export_job.error_message = None
    except Exception as exc:
        export_job.status = "failed"
        export_job.error_message = str(exc)
        export_job.completed_at = datetime.now(UTC)

    db.commit()
    db.refresh(export_job)
    return export_job
