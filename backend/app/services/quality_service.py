import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageFilter, ImageStat
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import DuplicateGroup, MediaAsset, QualitySignal


@dataclass(frozen=True)
class ImageQualityResult:
    blur_score: float
    quality_label: str
    image_width: int
    image_height: int
    perceptual_hash: str
    orientation: str | None = None
    exif_date_taken: datetime | None = None
    exif_camera_make: str | None = None
    exif_camera_model: str | None = None


@dataclass(frozen=True)
class DuplicateDetectionResult:
    perceptual_hash: str
    is_duplicate: bool
    duplicate_distance: int | None = None
    duplicate_group_id: uuid.UUID | None = None


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


def calculate_perceptual_hash(image: Image.Image) -> str:
    grayscale = image.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(grayscale.getdata())
    average_pixel = sum(pixels) / len(pixels)
    bits = ["1" if pixel >= average_pixel else "0" for pixel in pixels]
    return f"{int(''.join(bits), 2):016x}"


def hamming_distance(left_hash: str, right_hash: str) -> int:
    return (int(left_hash, 16) ^ int(right_hash, 16)).bit_count()


def analyze_image_quality(image_path: str | Path) -> ImageQualityResult:
    settings = get_settings()

    with Image.open(image_path) as image:
        image.load()
        width, height = image.size
        exif = _read_exif(image)
        blur_score = calculate_blur_score(image)
        perceptual_hash = calculate_perceptual_hash(image)

    return ImageQualityResult(
        blur_score=blur_score,
        quality_label=classify_blur_score(
            blur_score,
            blurry_threshold=settings.blur_threshold_blurry,
            acceptable_threshold=settings.blur_threshold_acceptable,
        ),
        image_width=width,
        image_height=height,
        perceptual_hash=perceptual_hash,
        orientation=_string_or_none(exif.get("Orientation")),
        exif_date_taken=_parse_exif_datetime(exif.get("DateTimeOriginal")),
        exif_camera_make=_string_or_none(exif.get("Make")),
        exif_camera_model=_string_or_none(exif.get("Model")),
    )


def detect_duplicate_for_media(
    db: Session,
    media_id: uuid.UUID,
    event_id: uuid.UUID,
    perceptual_hash: str,
    batch_job_id: uuid.UUID | None = None,
    commit: bool = True,
) -> DuplicateDetectionResult:
    settings = get_settings()
    threshold = settings.phash_duplicate_threshold
    quality_signal = _get_quality_signal(db, media_id)
    lock_event_for_duplicate_detection(db, event_id)

    best_match: tuple[QualitySignal, MediaAsset, int] | None = None
    rows = db.execute(
        select(QualitySignal, MediaAsset)
        .join(QualitySignal.media)
        .where(MediaAsset.event_id == event_id)
        .where(QualitySignal.media_id != media_id)
        .where(QualitySignal.perceptual_hash.is_not(None))
        .order_by(MediaAsset.created_at.asc(), MediaAsset.id.asc())
    ).all()

    for candidate_signal, candidate_media in rows:
        if candidate_signal.perceptual_hash is None:
            continue

        distance = hamming_distance(perceptual_hash, candidate_signal.perceptual_hash)
        if distance <= threshold and (
            best_match is None or distance < best_match[2]
        ):
            best_match = (candidate_signal, candidate_media, distance)

    if best_match is None:
        result = reset_duplicate_marker(quality_signal, perceptual_hash)
    else:
        matched_signal, matched_media, distance = best_match
        duplicate_group = _ensure_duplicate_group(
            db,
            event_id=event_id,
            batch_job_id=batch_job_id,
            representative_media_id=matched_media.id,
            matched_signal=matched_signal,
            threshold=threshold,
        )
        result = mark_duplicate_signal(
            quality_signal,
            duplicate_group_id=duplicate_group.id,
            perceptual_hash=perceptual_hash,
            duplicate_distance=distance,
        )
        _refresh_duplicate_group_size(db, duplicate_group)

    if commit:
        db.commit()
        db.refresh(quality_signal)

    return result


def lock_event_for_duplicate_detection(db: Session, event_id: uuid.UUID) -> None:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return

    db.execute(
        text("select pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _event_advisory_lock_key(event_id)},
    )


def _event_advisory_lock_key(event_id: uuid.UUID) -> int:
    return int.from_bytes(event_id.bytes[:8], byteorder="big", signed=True)


def reset_duplicate_marker(
    quality_signal: QualitySignal,
    perceptual_hash: str,
) -> DuplicateDetectionResult:
    quality_signal.perceptual_hash = perceptual_hash
    quality_signal.is_duplicate = False
    quality_signal.duplicate_distance = None
    quality_signal.duplicate_group_id = None
    return DuplicateDetectionResult(
        perceptual_hash=perceptual_hash,
        is_duplicate=False,
    )


def mark_duplicate_signal(
    quality_signal: QualitySignal,
    duplicate_group_id: uuid.UUID,
    perceptual_hash: str,
    duplicate_distance: int,
) -> DuplicateDetectionResult:
    quality_signal.perceptual_hash = perceptual_hash
    quality_signal.is_duplicate = True
    quality_signal.duplicate_distance = duplicate_distance
    quality_signal.duplicate_group_id = duplicate_group_id
    return DuplicateDetectionResult(
        perceptual_hash=perceptual_hash,
        is_duplicate=True,
        duplicate_distance=duplicate_distance,
        duplicate_group_id=duplicate_group_id,
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
    quality_signal.perceptual_hash = result.perceptual_hash
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


def _get_quality_signal(db: Session, media_id: uuid.UUID) -> QualitySignal:
    quality_signal = db.scalar(
        select(QualitySignal).where(QualitySignal.media_id == media_id)
    )
    if quality_signal is None:
        quality_signal = QualitySignal(media_id=media_id)
        db.add(quality_signal)
    return quality_signal


def _ensure_duplicate_group(
    db: Session,
    event_id: uuid.UUID,
    batch_job_id: uuid.UUID | None,
    representative_media_id: uuid.UUID,
    matched_signal: QualitySignal,
    threshold: int,
) -> DuplicateGroup:
    if matched_signal.duplicate_group_id is not None:
        existing_group = db.scalar(
            select(DuplicateGroup).where(
                DuplicateGroup.id == matched_signal.duplicate_group_id
            )
        )
        if existing_group is not None:
            return existing_group

    duplicate_group = DuplicateGroup(
        id=uuid.uuid4(),
        event_id=event_id,
        batch_job_id=batch_job_id,
        representative_media_id=representative_media_id,
        hash_algorithm="average_hash_8x8",
        threshold=threshold,
        group_size=2,
    )
    db.add(duplicate_group)
    matched_signal.duplicate_group_id = duplicate_group.id
    return duplicate_group


def _refresh_duplicate_group_size(
    db: Session,
    duplicate_group: DuplicateGroup,
) -> None:
    group_size = db.scalar(
        select(func.count())
        .select_from(QualitySignal)
        .where(QualitySignal.duplicate_group_id == duplicate_group.id)
    ) or 0
    duplicate_group.group_size = max(2, group_size)


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
