import hashlib
import math
import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MediaAsset, MediaEmbedding, QualitySignal, ReviewDecision

MEDIA_EMBEDDING_DIMENSION = 384


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str

    def embed_text(self, text: str) -> list[float]:
        ...


@dataclass(frozen=True)
class SearchResult:
    media: MediaAsset
    score: float


@dataclass(frozen=True)
class SearchFilters:
    include_duplicates: bool = False
    include_blurry: bool = True
    include_pending: bool = False
    export_ready_only: bool = True


class MockEmbeddingProvider:
    provider_name = "mock"

    def __init__(self, dimension: int | None = None) -> None:
        settings = get_settings()
        self.model_name = settings.embedding_model
        self.dimension = dimension or settings.embedding_dimension or MEDIA_EMBEDDING_DIMENSION

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


class SentenceTransformersEmbeddingProvider:
    provider_name = "sentence-transformers"

    def __init__(self, model_name: str | None = None, dimension: int | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.dimension = dimension or settings.embedding_dimension or MEDIA_EMBEDDING_DIMENSION
        self._model = _load_sentence_transformers_model(self.model_name)

    def embed_text(self, text: str) -> list[float]:
        vector = self._model.encode([text], normalize_embeddings=True)[0]
        values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        if len(values) != self.dimension:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"expected {self.dimension}, got {len(values)} for {self.model_name}."
            )
        return values


def _load_sentence_transformers_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ValueError(
            "SentenceTransformers provider requires sentence-transformers. "
            "Install with `pip install sentence-transformers`."
        ) from exc
    return SentenceTransformer(model_name)


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "mock":
        return MockEmbeddingProvider()
    if settings.embedding_provider == "sentence-transformers":
        return SentenceTransformersEmbeddingProvider()

    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


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
    provider: EmbeddingProvider | None = None,
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
    filters: SearchFilters | None = None,
    provider: EmbeddingProvider | None = None,
) -> list[SearchResult]:
    provider = provider or get_embedding_provider()
    filters = filters or SearchFilters()
    query_embedding = provider.embed_text(query)
    distance = MediaEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
        select(MediaAsset, distance)
        .join(MediaAsset.media_embedding)
        .outerjoin(MediaAsset.quality_signal)
        .outerjoin(MediaAsset.review_decision)
        .where(MediaAsset.event_id == event_id)
    )
    statement = apply_search_filters(statement, filters)

    rows = db.execute(
        statement.order_by(distance.asc(), MediaAsset.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return [
        SearchResult(media=media, score=max(0.0, 1.0 - float(distance_value)))
        for media, distance_value in rows
    ]


def count_searchable_event_media(
    db: Session,
    event_id: uuid.UUID,
    filters: SearchFilters | None = None,
) -> int:
    filters = filters or SearchFilters()
    statement = (
        select(func.count())
        .select_from(MediaEmbedding)
        .join(MediaEmbedding.media)
        .outerjoin(MediaAsset.quality_signal)
        .outerjoin(MediaAsset.review_decision)
        .where(MediaAsset.event_id == event_id)
    )
    statement = apply_search_filters(statement, filters)

    return db.scalar(statement) or 0


def apply_search_filters(statement, filters: SearchFilters):
    if not filters.include_duplicates:
        statement = statement.where(
            (QualitySignal.id.is_(None)) | (QualitySignal.is_duplicate.is_(False))
        )

    if not filters.include_blurry:
        statement = statement.where(
            (QualitySignal.id.is_(None))
            | (QualitySignal.quality_label.is_(None))
            | (QualitySignal.quality_label != "blurry")
        )

    if not filters.include_pending:
        statement = statement.where(
            (ReviewDecision.id.is_(None)) | (ReviewDecision.status != "pending")
        )

    if filters.export_ready_only:
        statement = statement.where(
            ReviewDecision.status.in_(("approved", "edited")),
            ReviewDecision.include_in_export.is_(True),
        )

    return statement
