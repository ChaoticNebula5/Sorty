import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.models import Event, MediaAsset, QualitySignal
from app.services import media_service
from app.services.media_service import (
    build_original_object_key,
    build_thumbnail_object_key,
)


def test_build_original_object_key() -> None:
    event_id = uuid.uuid4()
    media_id = uuid.uuid4()

    key = build_original_object_key(event_id, media_id, ".jpg")

    assert key == f"events/{event_id}/originals/{media_id}.jpg"


def test_build_thumbnail_object_key() -> None:
    event_id = uuid.uuid4()
    media_id = uuid.uuid4()

    key = build_thumbnail_object_key(event_id, media_id)

    assert key == f"events/{event_id}/thumbnails/{media_id}.jpg"


def test_get_event_media_summary_counts_media_quality_and_review_rows() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Event.metadata.create_all(
        engine,
        tables=[
            Event.__table__,
            MediaAsset.__table__,
            QualitySignal.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)

    with Session() as db:
        db.execute(
            text(
                "create table review_decisions ("
                "id char(32) primary key, "
                "media_id char(32) not null, "
                "status varchar(40) not null, "
                "include_in_export boolean not null"
                ")"
            )
        )
        event = Event(name="Campus Fest", slug="campus-fest")
        other_event = Event(name="Other Fest", slug="other-fest")
        db.add_all([event, other_event])
        db.flush()

        processed = _make_media(event.id, "processed.jpg", "processed")
        blurry = _make_media(event.id, "blurry.jpg", "needs_review")
        duplicate = _make_media(event.id, "duplicate.jpg", "needs_review")
        failed = _make_media(event.id, "failed.jpg", "failed")
        edited = _make_media(event.id, "edited.jpg", "processed")
        other = _make_media(other_event.id, "other.jpg", "needs_review")
        db.add_all([processed, blurry, duplicate, failed, edited, other])
        db.flush()
        db.add_all(
            [
                QualitySignal(media_id=processed.id, quality_label="sharp"),
                QualitySignal(media_id=blurry.id, quality_label="blurry"),
                QualitySignal(
                    media_id=duplicate.id,
                    quality_label="acceptable",
                    is_duplicate=True,
                ),
                QualitySignal(media_id=other.id, quality_label="blurry", is_duplicate=True),
            ]
        )
        for media, status, include_in_export in (
            (processed, "approved", True),
            (blurry, "pending", False),
            (failed, "rejected", False),
            (duplicate, "duplicate", False),
            (edited, "edited", True),
            (other, "pending", True),
        ):
            db.execute(
                text(
                    "insert into review_decisions "
                    "(id, media_id, status, include_in_export) "
                    "values (:id, :media_id, :status, :include_in_export)"
                ),
                {
                    "id": uuid.uuid4().hex,
                    "media_id": media.id.hex,
                    "status": status,
                    "include_in_export": include_in_export,
                },
            )
        db.commit()

        summary = media_service.get_event_media_summary(db, event.id)

    assert summary.event_id == event.id
    assert summary.total_media == 5
    assert summary.processed_media == 2
    assert summary.needs_review_media == 2
    assert summary.failed_media == 1
    assert summary.blurry_media == 1
    assert summary.possible_duplicate_media == 1
    assert summary.pending_review_decisions == 1
    assert summary.approved_review_decisions == 1
    assert summary.edited_review_decisions == 1
    assert summary.rejected_review_decisions == 1
    assert summary.confirmed_duplicate_decisions == 1
    assert summary.export_ready_review_decisions == 2


def _make_media(
    event_id: uuid.UUID,
    filename: str,
    processing_status: str,
) -> MediaAsset:
    media_id = uuid.uuid4()
    now = datetime.now(UTC)
    return MediaAsset(
        id=media_id,
        event_id=event_id,
        original_filename=filename,
        stored_filename=f"{media_id}.jpg",
        bucket_name="sorty-media",
        original_object_key=f"events/{event_id}/originals/{media_id}.jpg",
        thumbnail_object_key=f"events/{event_id}/thumbnails/{media_id}.jpg",
        mime_type="image/jpeg",
        file_extension=".jpg",
        size_bytes=100,
        upload_status="accepted",
        processing_status=processing_status,
        created_at=now,
        updated_at=now,
    )
