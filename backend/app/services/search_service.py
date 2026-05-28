import hashlib
import math
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MediaAsset, MediaEmbedding

MEDIA_EMBEDDING_DIMENSION = 384


@dataclass(frozen=True)
class SearchResult:
    media: MediaAsset
    score: float


class MockEmbeddingProvider:
    provider_name = "mock"

    def __init__(self, dimension: int | None = None) -> None:
        settings = get_settings()
        self.model_name = settings.embedding_model
        self.dimension = dimension or MEDIA_EMBEDDING_DIMENSION

    def embed_text(self, text: str) -> list[float]:
        normalized_text = " ".join(text.lower().split())
        values: list[float] = []

        counter = 0
        while len(values) < self.dimension:
            digest = hashlib.sha256(f"{normalized_text}:{counter}".encode()).digest()
            for byte in digest:
                values.append((byte / 127.5) - 1.0)
                if len(values) == self.dimension:
                    break
            counter += 1

        magnitude = math.sqrt(sum(value * value for value in values))
        if magnitude == 0:
            return values
        return [value / magnitude for value in values]


def get_embedding_provider() -> MockEmbeddingProvider:
    return MockEmbeddingProvider()


def build_indexed_text(media: MediaAsset) -> str:
    analysis = getattr(media, "ai_analysis", None)
    review = getattr(media, "review_decision", None)
    quality = getattr(media, "quality_signal", None)

    parts = [
        media.original_filename,
        getattr(analysis, "caption", None),
        getattr(analysis, "primary_subject", None),
        getattr(analysis, "scene_type", None),
        getattr(analysis, "event_context", None),
        getattr(review, "final_primary_folder", None)
        or getattr(analysis, "suggested_primary_folder", None),
        getattr(review, "final_sub_folder", None)
        or getattr(analysis, "suggested_sub_folder", None),
        getattr(quality, "quality_label", None),
        getattr(review, "reviewer_note", None),
    ]

    tags = list(getattr(analysis, "tags", []) or [])
    final_tags = list(getattr(review, "final_tags", []) or [])
    review_reasons = list(getattr(review, "review_reasons", []) or [])

    return " ".join(
        str(part).strip()
        for part in [*parts, *tags, *final_tags, *review_reasons]
        if part is not None and str(part).strip()
    )


def upsert_media_embedding(
    db: Session,
    media: MediaAsset,
    provider: MockEmbeddingProvider | None = None,
    commit: bool = True,
) -> MediaEmbedding:
    provider = provider or get_embedding_provider()
    indexed_text = build_indexed_text(media)
    embedding_vector = provider.embed_text(indexed_text)

    embedding = db.scalar(
        select(MediaEmbedding).where(MediaEmbedding.media_id == media.id)
    )
    if embedding is None:
        embedding = MediaEmbedding(media_id=media.id)
        db.add(embedding)

    embedding.indexed_text = indexed_text
    embedding.embedding = embedding_vector
    embedding.embedding_model = provider.model_name

    if commit:
        db.commit()
        db.refresh(embedding)

    return embedding


def search_event_media(
    db: Session,
    event_id: uuid.UUID,
    query: str,
    limit: int = 20,
    offset: int = 0,
    provider: MockEmbeddingProvider | None = None,
) -> list[SearchResult]:
    provider = provider or get_embedding_provider()
    query_embedding = provider.embed_text(query)
    distance = MediaEmbedding.embedding.cosine_distance(query_embedding).label("distance")

    rows = db.execute(
        select(MediaAsset, distance)
        .join(MediaAsset.media_embedding)
        .where(MediaAsset.event_id == event_id)
        .order_by(distance.asc(), MediaAsset.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return [
        SearchResult(media=media, score=max(0.0, 1.0 - float(distance_value)))
        for media, distance_value in rows
    ]


def count_searchable_event_media(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(MediaEmbedding)
        .join(MediaEmbedding.media)
        .where(MediaAsset.event_id == event_id)
    ) or 0
