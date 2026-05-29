import uuid
from decimal import Decimal
from types import SimpleNamespace

from PIL import Image, ImageDraw
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import BatchJob, DuplicateGroup, Event, MediaAsset, QualitySignal
from app.services import quality_service


class FakeDb:
    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.added = None
        self.committed = False
        self.refreshed = None

    def scalar(self, statement):
        return self.existing

    def add(self, item) -> None:
        self.added = item

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item) -> None:
        self.refreshed = item


def test_classify_blur_score_uses_configured_thresholds() -> None:
    assert quality_service.classify_blur_score(12.0, 80, 150) == "blurry"
    assert quality_service.classify_blur_score(100.0, 80, 150) == "acceptable"
    assert quality_service.classify_blur_score(220.0, 80, 150) == "sharp"


def test_calculate_blur_score_is_higher_for_edge_rich_image() -> None:
    flat = Image.new("RGB", (64, 64), "white")
    detailed = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(detailed)
    for index in range(0, 64, 4):
        draw.line((index, 0, index, 63), fill="black")
        draw.line((0, index, 63, index), fill="black")

    assert (
        quality_service.calculate_blur_score(detailed)
        > quality_service.calculate_blur_score(flat)
    )


def test_analyze_image_quality_reads_dimensions(tmp_path) -> None:
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (40, 30), "white").save(image_path)

    result = quality_service.analyze_image_quality(image_path)

    assert result.image_width == 40
    assert result.image_height == 30
    assert result.quality_label in {"sharp", "acceptable", "blurry"}
    assert len(result.perceptual_hash) == 16


def test_perceptual_hash_distance_is_zero_for_matching_images() -> None:
    image = Image.new("RGB", (32, 32), "white")
    left_hash = quality_service.calculate_perceptual_hash(image)
    right_hash = quality_service.calculate_perceptual_hash(image.copy())

    assert left_hash == right_hash
    assert quality_service.hamming_distance(left_hash, right_hash) == 0


def test_upsert_quality_signal_creates_row_without_commit() -> None:
    db = FakeDb()
    media_id = uuid.uuid4()
    result = quality_service.ImageQualityResult(
        blur_score=42.12345,
        quality_label="blurry",
        image_width=120,
        image_height=80,
        perceptual_hash="f" * 16,
        orientation="1",
        exif_camera_make="Canon",
        exif_camera_model="M50",
    )

    quality_signal = quality_service.upsert_quality_signal(
        db,
        media_id=media_id,
        result=result,
        commit=False,
    )

    assert db.added is quality_signal
    assert db.committed is False
    assert quality_signal.media_id == media_id
    assert quality_signal.blur_score == Decimal("42.1234")
    assert quality_signal.quality_label == "blurry"
    assert quality_signal.perceptual_hash == "f" * 16
    assert quality_signal.image_width == 120
    assert quality_signal.image_height == 80
    assert quality_signal.exif_camera_make == "Canon"


def test_upsert_quality_signal_updates_existing_row_with_commit() -> None:
    existing = SimpleNamespace()
    db = FakeDb(existing=existing)
    result = quality_service.ImageQualityResult(
        blur_score=160.0,
        quality_label="sharp",
        image_width=10,
        image_height=10,
        perceptual_hash="0" * 16,
    )

    quality_signal = quality_service.upsert_quality_signal(
        db,
        media_id=uuid.uuid4(),
        result=result,
        commit=True,
    )

    assert quality_signal is existing
    assert db.added is None
    assert db.committed is True
    assert db.refreshed is existing
    assert existing.quality_label == "sharp"


def test_reset_duplicate_marker_clears_duplicate_fields() -> None:
    quality_signal = SimpleNamespace(
        perceptual_hash="f" * 16,
        is_duplicate=True,
        duplicate_distance=2,
        duplicate_group_id=uuid.uuid4(),
    )

    result = quality_service.reset_duplicate_marker(
        quality_signal,
        perceptual_hash="0" * 16,
    )

    assert result.is_duplicate is False
    assert quality_signal.perceptual_hash == "0" * 16
    assert quality_signal.is_duplicate is False
    assert quality_signal.duplicate_distance is None
    assert quality_signal.duplicate_group_id is None


def test_mark_duplicate_signal_sets_duplicate_fields() -> None:
    quality_signal = SimpleNamespace()
    group_id = uuid.uuid4()

    result = quality_service.mark_duplicate_signal(
        quality_signal,
        duplicate_group_id=group_id,
        perceptual_hash="a" * 16,
        duplicate_distance=3,
    )

    assert result.is_duplicate is True
    assert result.duplicate_group_id == group_id
    assert result.duplicate_distance == 3
    assert quality_signal.perceptual_hash == "a" * 16
    assert quality_signal.is_duplicate is True
    assert quality_signal.duplicate_group_id == group_id
    assert quality_signal.duplicate_distance == 3


def test_detect_duplicate_for_media_creates_duplicate_group() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Event.metadata.create_all(
        engine,
        tables=[
            Event.__table__,
            BatchJob.__table__,
            MediaAsset.__table__,
            DuplicateGroup.__table__,
            QualitySignal.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)

    with Session() as db:
        event = Event(name="Campus Fest", slug="campus-fest")
        db.add(event)
        db.flush()
        original = _make_media(event.id, "original.jpg")
        duplicate = _make_media(event.id, "duplicate.jpg")
        db.add_all([original, duplicate])
        db.flush()
        db.add_all(
            [
                QualitySignal(media_id=original.id, perceptual_hash="0" * 16),
                QualitySignal(media_id=duplicate.id),
            ]
        )
        db.commit()

        result = quality_service.detect_duplicate_for_media(
            db,
            media_id=duplicate.id,
            event_id=event.id,
            perceptual_hash="0" * 16,
            commit=True,
        )

        duplicate_signal = db.scalar(
            select(QualitySignal).where(QualitySignal.media_id == duplicate.id)
        )
        original_signal = db.scalar(
            select(QualitySignal).where(QualitySignal.media_id == original.id)
        )
        duplicate_group = db.scalar(select(DuplicateGroup))

    assert result.is_duplicate is True
    assert result.duplicate_distance == 0
    assert duplicate_signal is not None
    assert original_signal is not None
    assert duplicate_group is not None
    assert duplicate_signal.is_duplicate is True
    assert duplicate_signal.duplicate_group_id == duplicate_group.id
    assert original_signal.duplicate_group_id == duplicate_group.id
    assert duplicate_group.group_size == 2


def test_detect_duplicate_for_media_reuses_supplied_quality_signal(monkeypatch) -> None:
    media_id = uuid.uuid4()
    event_id = uuid.uuid4()
    quality_signal = SimpleNamespace(
        media_id=media_id,
        perceptual_hash=None,
        is_duplicate=False,
        duplicate_distance=None,
        duplicate_group_id=None,
    )

    class FakeResult:
        def all(self):
            return []

    class FakeDbNoFetch(FakeDb):
        def scalar(self, statement):
            raise AssertionError("quality signal should not be fetched again")

        def execute(self, statement):
            return FakeResult()

    monkeypatch.setattr(
        quality_service,
        "lock_event_for_duplicate_detection",
        lambda db, event_id: None,
    )

    result = quality_service.detect_duplicate_for_media(
        FakeDbNoFetch(),
        media_id=media_id,
        event_id=event_id,
        perceptual_hash="f" * 16,
        quality_signal=quality_signal,
        commit=False,
    )

    assert result.is_duplicate is False
    assert quality_signal.perceptual_hash == "f" * 16
    assert quality_signal.is_duplicate is False


def test_lock_event_for_duplicate_detection_skips_non_postgres_db() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Session = sessionmaker(bind=engine)

    with Session() as db:
        quality_service.lock_event_for_duplicate_detection(db, uuid.uuid4())


def _make_media(event_id: uuid.UUID, filename: str) -> MediaAsset:
    media_id = uuid.uuid4()
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
        processing_status="processed",
    )
