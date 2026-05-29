import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageFilter, ImageStat
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import QualitySignal


@dataclass(frozen=True)
class ImageQualityResult:
    blur_score: float
    quality_label: str
    image_width: int
    image_height: int
    orientation: str | None = None
    exif_date_taken: datetime | None = None
    exif_camera_make: str | None = None
    exif_camera_model: str | None = None


def classify_blur_score(
    blur_score: float,
    blurry_threshold: int,
    acceptable_threshold: int,
) -> str:
    if blur_score < blurry_threshold:
        return "blurry"
    if blur_score < acceptable_threshold:
        return "acceptable"
    return "sharp"


def calculate_blur_score(image: Image.Image) -> float:
    grayscale = image.convert("L")
    edge_image = grayscale.filter(ImageFilter.FIND_EDGES)
    return float(ImageStat.Stat(edge_image).var[0])


def analyze_image_quality(image_path: str | Path) -> ImageQualityResult:
    settings = get_settings()

    with Image.open(image_path) as image:
        image.load()
        width, height = image.size
        exif = _read_exif(image)
        blur_score = calculate_blur_score(image)

    return ImageQualityResult(
        blur_score=blur_score,
        quality_label=classify_blur_score(
            blur_score,
            blurry_threshold=settings.blur_threshold_blurry,
            acceptable_threshold=settings.blur_threshold_acceptable,
        ),
        image_width=width,
        image_height=height,
        orientation=_string_or_none(exif.get("Orientation")),
        exif_date_taken=_parse_exif_datetime(exif.get("DateTimeOriginal")),
        exif_camera_make=_string_or_none(exif.get("Make")),
        exif_camera_model=_string_or_none(exif.get("Model")),
    )


def upsert_quality_signal(
    db: Session,
    media_id: uuid.UUID,
    result: ImageQualityResult,
    commit: bool = True,
) -> QualitySignal:
    quality_signal = db.scalar(
        select(QualitySignal).where(QualitySignal.media_id == media_id)
    )
    if quality_signal is None:
        quality_signal = QualitySignal(media_id=media_id)
        db.add(quality_signal)

    quality_signal.blur_score = Decimal(str(round(result.blur_score, 4)))
    quality_signal.quality_label = result.quality_label
    quality_signal.image_width = result.image_width
    quality_signal.image_height = result.image_height
    quality_signal.orientation = result.orientation
    quality_signal.exif_date_taken = result.exif_date_taken
    quality_signal.exif_camera_make = result.exif_camera_make
    quality_signal.exif_camera_model = result.exif_camera_model

    if commit:
        db.commit()
        db.refresh(quality_signal)

    return quality_signal


def _read_exif(image: Image.Image) -> dict[str, Any]:
    raw_exif = image.getexif()
    if not raw_exif:
        return {}

    return {
        ExifTags.TAGS.get(tag_id, str(tag_id)): value
        for tag_id, value in raw_exif.items()
    }


def _parse_exif_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()
    return cleaned or None
