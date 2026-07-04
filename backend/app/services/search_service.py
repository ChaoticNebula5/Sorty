import hashlib
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    MediaAsset,
    MediaEmbedding,
    MediaVisualEmbedding,
    QualitySignal,
    ReviewDecision,
)

MEDIA_EMBEDDING_DIMENSION = 384
VISUAL_EMBEDDING_DIMENSION = 512
_sentence_transformers_model_lock = Lock()
_sentence_transformers_models: dict[str, object] = {}


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str

    def embed_text(self, text: str) -> list[float]:
        ...


class VisualEmbeddingProvider(Protocol):
    provider_name: str
    model_name: str

    def embed_text(self, text: str) -> list[float]:
        ...

    def embed_image(self, image_path: str | Path) -> list[float]:
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
    min_score: float = 0.3


class MockEmbeddingProvider:
    provider_name = "mock"

    def __init__(self, dimension: int | None = None) -> None:
        settings = get_settings()
        self.dimension = dimension or settings.embedding_dimension or MEDIA_EMBEDDING_DIMENSION
        self.model_name = f"mock:{settings.embedding_model}:{self.dimension}"

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


class SentenceTransformersVisualEmbeddingProvider:
    provider_name = "sentence-transformers-clip"

    def __init__(self, model_name: str | None = None, dimension: int | None = None) -> None:
        settings = get_settings()
        self.raw_model_name = model_name or settings.visual_embedding_model
        self.dimension = (
            dimension
            or settings.visual_embedding_dimension
            or VISUAL_EMBEDDING_DIMENSION
        )
        self.model_name = f"{self.provider_name}:{self.raw_model_name}:{self.dimension}"
        self._model = _load_sentence_transformers_model(self.raw_model_name)

    def embed_text(self, text: str) -> list[float]:
        return self._encode([text])

    def embed_image(self, image_path: str | Path) -> list[float]:
        from PIL import Image, ImageOps

        with Image.open(image_path) as image:
            normalized_image = ImageOps.exif_transpose(image).convert("RGB")
            return self._encode([normalized_image])

    def _encode(self, items: list[object]) -> list[float]:
        vector = self._model.encode(items, normalize_embeddings=True)[0]
        values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        if len(values) != self.dimension:
            raise ValueError(
                "Visual embedding dimension mismatch: "
                f"expected {self.dimension}, got {len(values)} for {self.raw_model_name}."
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

    with _sentence_transformers_model_lock:
        model = _sentence_transformers_models.get(model_name)
        if model is None:
            model = SentenceTransformer(model_name)
            _sentence_transformers_models[model_name] = model
        return model


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "mock":
        return MockEmbeddingProvider()
    if settings.embedding_provider == "sentence-transformers":
        return SentenceTransformersEmbeddingProvider()

    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


def get_visual_embedding_provider() -> VisualEmbeddingProvider | None:
    settings = get_settings()
    if not settings.visual_search_enabled:
        return None
    return SentenceTransformersVisualEmbeddingProvider()


def build_indexed_text(media: MediaAsset) -> str:
    # Metadata search embeds vision analysis and review decisions; visual search
    # adds CLIP image-text similarity when media_visual_embeddings are present.
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


def upsert_media_visual_embedding(
    db: Session,
    media: MediaAsset,
    image_path: str | Path,
    provider: VisualEmbeddingProvider | None = None,
    commit: bool = True,
) -> MediaVisualEmbedding | None:
    provider = provider or get_visual_embedding_provider()
    if provider is None:
        return None

    embedding_vector = provider.embed_image(image_path)
    embedding = db.scalar(
        select(MediaVisualEmbedding).where(MediaVisualEmbedding.media_id == media.id)
    )
    if embedding is None:
        embedding = MediaVisualEmbedding(media_id=media.id)
        db.add(embedding)

    embedding.embedding = embedding_vector
    embedding.embedding_model = provider.model_name

    if commit:
        db.commit()
        db.refresh(embedding)

    return embedding


def list_media_missing_visual_embeddings(
    db: Session,
    event_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[MediaAsset]:
    statement = (
        select(MediaAsset)
        .outerjoin(MediaAsset.media_visual_embedding)
        .where(MediaVisualEmbedding.id.is_(None))
        .order_by(MediaAsset.created_at.asc())
        .limit(limit)
    )
    if event_id is not None:
        statement = statement.where(MediaAsset.event_id == event_id)

    return list(db.scalars(statement))


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
    result_limit = max(limit + offset, limit)
    text_rows = _search_text_rows(
        db,
        event_id=event_id,
        query_embedding=query_embedding,
        provider_model_name=provider.model_name,
        filters=filters,
        limit=result_limit,
    )

    visual_rows: list[tuple[MediaAsset, float]] = []
    try:
        visual_provider = get_visual_embedding_provider()
        if visual_provider is not None:
            with db.begin_nested():
                visual_rows = _search_visual_rows(
                    db,
                    event_id=event_id,
                    query_embedding=visual_provider.embed_text(query),
                    provider_model_name=visual_provider.model_name,
                    filters=filters,
                    limit=result_limit,
                )
    except Exception:
        visual_rows = []

    return _combine_search_rows(text_rows, visual_rows)[offset : offset + limit]


def _search_text_rows(
    db: Session,
    event_id: uuid.UUID,
    query_embedding: list[float],
    provider_model_name: str,
    filters: SearchFilters,
    limit: int,
) -> list[tuple[MediaAsset, float]]:
    distance = MediaEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    statement = _search_text_statement(
        event_id=event_id,
        query_embedding=query_embedding,
        provider_model_name=provider_model_name,
        filters=filters,
        selected_columns=(MediaAsset, distance),
    )
    rows = db.execute(
        statement.order_by(distance.asc(), MediaAsset.created_at.desc())
        .limit(limit)
    ).all()

    return [
        (media, max(0.0, 1.0 - float(distance_value)))
        for media, distance_value in rows
    ]


def _search_text_statement(
    event_id: uuid.UUID,
    query_embedding: list[float],
    provider_model_name: str,
    filters: SearchFilters,
    selected_columns: tuple[object, ...],
):
    distance = MediaEmbedding.embedding.cosine_distance(query_embedding)
    statement = (
        select(*selected_columns)
        .join(MediaAsset.media_embedding)
        .outerjoin(MediaAsset.quality_signal)
        .outerjoin(MediaAsset.review_decision)
        .where(
            MediaAsset.event_id == event_id,
            MediaEmbedding.embedding_model == provider_model_name,
        )
    )
    statement = apply_search_filters(statement, filters)
    if filters.min_score > 0:
        statement = statement.where(distance <= (1.0 - filters.min_score))
    return statement


def _search_visual_rows(
    db: Session,
    event_id: uuid.UUID,
    query_embedding: list[float],
    provider_model_name: str,
    filters: SearchFilters,
    limit: int,
) -> list[tuple[MediaAsset, float]]:
    distance = MediaVisualEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    statement = _search_visual_statement(
        event_id=event_id,
        query_embedding=query_embedding,
        provider_model_name=provider_model_name,
        filters=filters,
        selected_columns=(MediaAsset, distance),
    )
    rows = db.execute(
        statement.order_by(distance.asc(), MediaAsset.created_at.desc()).limit(limit)
    ).all()

    return [
        (media, max(0.0, 1.0 - float(distance_value)))
        for media, distance_value in rows
    ]


def _search_visual_statement(
    event_id: uuid.UUID,
    query_embedding: list[float],
    provider_model_name: str,
    filters: SearchFilters,
    selected_columns: tuple[object, ...],
):
    settings = get_settings()
    visual_min_score = max(filters.min_score, settings.visual_search_min_score)
    distance = MediaVisualEmbedding.embedding.cosine_distance(query_embedding)
    statement = (
        select(*selected_columns)
        .join(MediaAsset.media_visual_embedding)
        .outerjoin(MediaAsset.quality_signal)
        .outerjoin(MediaAsset.review_decision)
        .where(
            MediaAsset.event_id == event_id,
            MediaVisualEmbedding.embedding_model == provider_model_name,
        )
    )
    statement = apply_search_filters(statement, filters)
    if visual_min_score > 0:
        statement = statement.where(distance <= (1.0 - visual_min_score))
    return statement


def _combine_search_rows(
    text_rows: list[tuple[MediaAsset, float]],
    visual_rows: list[tuple[MediaAsset, float]],
) -> list[SearchResult]:
    settings = get_settings()
    visual_weight = max(0.0, min(1.0, settings.visual_search_weight))
    combined: dict[uuid.UUID, dict[str, object]] = {}

    for media, score in text_rows:
        combined.setdefault(
            media.id,
            {"media": media, "text_score": 0.0, "visual_score": None},
        )
        combined[media.id]["text_score"] = max(
            float(combined[media.id]["text_score"]),
            score,
        )

    for media, score in visual_rows:
        combined.setdefault(
            media.id,
            {"media": media, "text_score": 0.0, "visual_score": None},
        )
        current_visual_score = combined[media.id]["visual_score"]
        combined[media.id]["visual_score"] = max(
            float(current_visual_score) if current_visual_score is not None else 0.0,
            score,
        )

    results: list[SearchResult] = []
    for row in combined.values():
        text_score = float(row["text_score"])
        visual_score = row["visual_score"]
        score = text_score
        if visual_score is not None and text_score > 0:
            score = (visual_weight * float(visual_score)) + (
                (1.0 - visual_weight) * text_score
            )
        elif visual_score is not None:
            score = float(visual_score)
        results.append(SearchResult(media=row["media"], score=score))

    return sorted(results, key=lambda result: result.score, reverse=True)


def count_searchable_event_media(
    db: Session,
    event_id: uuid.UUID,
    query: str | None = None,
    filters: SearchFilters | None = None,
    provider: EmbeddingProvider | None = None,
) -> int:
    provider = provider or get_embedding_provider()
    filters = filters or SearchFilters()
    if query is not None:
        try:
            visual_provider = get_visual_embedding_provider()
            if visual_provider is not None:
                query_embedding = provider.embed_text(query)
                visual_query_embedding = visual_provider.embed_text(query)
                text_statement = _search_text_statement(
                    event_id=event_id,
                    query_embedding=query_embedding,
                    provider_model_name=provider.model_name,
                    filters=filters,
                    selected_columns=(MediaAsset.id,),
                )
                visual_statement = _search_visual_statement(
                    event_id=event_id,
                    query_embedding=visual_query_embedding,
                    provider_model_name=visual_provider.model_name,
                    filters=filters,
                    selected_columns=(MediaAsset.id,),
                )
                text_ids = set(db.scalars(text_statement))
                with db.begin_nested():
                    visual_ids = set(db.scalars(visual_statement))
                return len(text_ids | visual_ids)
        except Exception:
            pass

    statement = (
        select(func.count())
        .select_from(MediaEmbedding)
        .join(MediaEmbedding.media)
        .outerjoin(MediaAsset.quality_signal)
        .outerjoin(MediaAsset.review_decision)
        .where(
            MediaAsset.event_id == event_id,
            MediaEmbedding.embedding_model == provider.model_name,
        )
    )
    statement = apply_search_filters(statement, filters)
    if query is not None and filters.min_score > 0:
        query_embedding = provider.embed_text(query)
        distance = MediaEmbedding.embedding.cosine_distance(query_embedding)
        statement = statement.where(distance <= (1.0 - filters.min_score))

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
