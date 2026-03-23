"""
AssetMetadata ORM model.
Stores AI-generated metadata and enrichment results for assets.
See PRD §6 (Database Schema) and §7 (Data Models).
"""

from uuid import UUID
from sqlalchemy import (
    ForeignKey,
    Text,
    SmallInteger,
    Float,
    Boolean,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from pgvector.sqlalchemy import Vector
from backend.database import Base


class AssetMetadata(Base):
    __tablename__ = "asset_metadata"

    # Table-level constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "usefulness_score BETWEEN 0 AND 100", name="ck_usefulness_score_range"
        ),
        CheckConstraint(
            "sponsor_visible_score BETWEEN 0.0 AND 1.0", name="ck_sponsor_score_range"
        ),
        Index(
            "idx_asset_metadata_embedding",
            "embedding_vector",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding_vector": "vector_cosine_ops"},
        ),
        Index("idx_asset_metadata_fts", "fts_vector", postgresql_using="gin"),
        Index("idx_asset_metadata_tags", "tags_json", postgresql_using="gin"),
    )

    # Primary key (also foreign key to assets)
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )

    # AI-generated content
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    # Category classification
    primary_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_scores_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # CLIP embedding vector (512-dim)
    embedding_vector: Mapped[list[float] | None] = mapped_column(
        Vector(512), nullable=True
    )

    # Quality scores
    usefulness_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    brightness_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Sponsor visibility score
    sponsor_visible_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Flags
    duplicate_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    low_quality_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    # Full-text search vector (populated by trigger)
    fts_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    asset: Mapped["Asset"] = relationship("Asset", back_populates="asset_metadata")

    def __repr__(self) -> str:
        return f"<AssetMetadata(asset_id={self.asset_id}, usefulness={self.usefulness_score})>"
