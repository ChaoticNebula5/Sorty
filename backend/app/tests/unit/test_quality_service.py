import uuid
from decimal import Decimal
from types import SimpleNamespace

from PIL import Image, ImageDraw

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


def test_upsert_quality_signal_creates_row_without_commit() -> None:
    db = FakeDb()
    media_id = uuid.uuid4()
    result = quality_service.ImageQualityResult(
        blur_score=42.12345,
        quality_label="blurry",
        image_width=120,
        image_height=80,
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
