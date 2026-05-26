import uuid
from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("length(name) >= 2", name="ck_events_name_min_length"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    event_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    batch_jobs: Mapped[list["BatchJob"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )
    media_assets: Mapped[list["MediaAsset"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )
    duplicate_groups: Mapped[list["DuplicateGroup"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )
    export_jobs: Mapped[list["ExportJob"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )


class BatchJob(TimestampMixin, Base):
    __tablename__ = "batch_jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ("
            "'created', 'queued', 'processing', 'waiting_for_review', "
            "'reviewed', 'exporting', 'completed', 'failed', 'partial_failed'"
            ")",
            name="ck_batch_jobs_status",
        ),
        CheckConstraint("total_files >= 0", name="ck_batch_jobs_total_files"),
        CheckConstraint("processed_files >= 0", name="ck_batch_jobs_processed_files"),
        CheckConstraint("failed_files >= 0", name="ck_batch_jobs_failed_files"),
        CheckConstraint(
            "needs_review_count >= 0",
            name="ck_batch_jobs_needs_review_count",
        ),
        UniqueConstraint("langgraph_thread_id", name="uq_batch_jobs_thread_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    langgraph_thread_id: Mapped[str] = mapped_column(String(120), nullable=False)
    current_rq_job_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="created")
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="batch_jobs")
    media_assets: Mapped[list["MediaAsset"]] = relationship(back_populates="batch_job")
    duplicate_groups: Mapped[list["DuplicateGroup"]] = relationship(
        back_populates="batch_job",
    )


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint(
            "upload_status in ('accepted', 'rejected')",
            name="ck_media_assets_upload_status",
        ),
        CheckConstraint(
            "processing_status in ("
            "'uploaded', 'queued', 'processing', 'processed', "
            "'needs_review', 'failed', 'excluded'"
            ")",
            name="ck_media_assets_processing_status",
        ),
        CheckConstraint("size_bytes > 0", name="ck_media_assets_size_bytes"),
        CheckConstraint(
            "file_extension in ('.jpg', '.jpeg', '.png', '.webp')",
            name="ck_media_assets_file_extension",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    batch_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batch_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    original_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(12), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upload_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="accepted",
    )
    processing_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="uploaded",
    )
    upload_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="media_assets")
    batch_job: Mapped[BatchJob | None] = relationship(back_populates="media_assets")
    ai_analysis: Mapped["AIAnalysis | None"] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )
    quality_signal: Mapped["QualitySignal | None"] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )
    review_decision: Mapped["ReviewDecision | None"] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )
    media_embedding: Mapped["MediaEmbedding | None"] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(tags) = 'array'",
            name="ck_ai_analyses_tags_array",
        ),
        CheckConstraint(
            "folder_confidence is null or "
            "(folder_confidence >= 0 and folder_confidence <= 1)",
            name="ck_ai_analyses_folder_confidence",
        ),
        CheckConstraint(
            "validation_status in ('valid', 'fallback', 'invalid')",
            name="ck_ai_analyses_validation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_subject: Mapped[str | None] = mapped_column(String(160), nullable=True)
    scene_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    people_count: Mapped[str | None] = mapped_column(String(40), nullable=True)
    event_context: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    suggested_primary_folder: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    suggested_sub_folder: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    folder_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3),
        nullable=True,
    )
    folder_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    media: Mapped[MediaAsset] = relationship(back_populates="ai_analysis")


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"
    __table_args__ = (
        CheckConstraint("threshold >= 0", name="ck_duplicate_groups_threshold"),
        CheckConstraint("group_size >= 2", name="ck_duplicate_groups_group_size"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    batch_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batch_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    representative_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    hash_algorithm: Mapped[str] = mapped_column(String(40), nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    group_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    event: Mapped[Event] = relationship(back_populates="duplicate_groups")
    batch_job: Mapped[BatchJob | None] = relationship(back_populates="duplicate_groups")
    quality_signals: Mapped[list["QualitySignal"]] = relationship(
        back_populates="duplicate_group",
    )


class QualitySignal(Base):
    __tablename__ = "quality_signals"
    __table_args__ = (
        CheckConstraint(
            "quality_label is null or quality_label in "
            "('sharp', 'acceptable', 'blurry')",
            name="ck_quality_signals_quality_label",
        ),
        CheckConstraint(
            "image_width is null or image_width > 0",
            name="ck_quality_signals_image_width",
        ),
        CheckConstraint(
            "image_height is null or image_height > 0",
            name="ck_quality_signals_image_height",
        ),
        CheckConstraint(
            "duplicate_distance is null or duplicate_distance >= 0",
            name="ck_quality_signals_duplicate_distance",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    blur_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    quality_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    perceptual_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duplicate_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("duplicate_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_distance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exif_date_taken: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    exif_camera_make: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exif_camera_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    media: Mapped[MediaAsset] = relationship(back_populates="quality_signal")
    duplicate_group: Mapped[DuplicateGroup | None] = relationship(
        back_populates="quality_signals",
    )


class ReviewDecision(TimestampMixin, Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'approved', 'edited', 'rejected', 'duplicate')",
            name="ck_review_decisions_status",
        ),
        CheckConstraint(
            "jsonb_typeof(final_tags) = 'array'",
            name="ck_review_decisions_final_tags_array",
        ),
        CheckConstraint(
            "jsonb_typeof(review_reasons) = 'array'",
            name="ck_review_decisions_review_reasons_array",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    final_primary_folder: Mapped[str | None] = mapped_column(String(120), nullable=True)
    final_sub_folder: Mapped[str | None] = mapped_column(String(120), nullable=True)
    final_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    include_in_export: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    review_reasons: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    media: Mapped[MediaAsset] = relationship(back_populates="review_decision")


class MediaEmbedding(Base):
    __tablename__ = "media_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    indexed_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    media: Mapped[MediaAsset] = relationship(back_populates="media_embedding")


class ExportJob(Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ('created', 'queued', 'exporting', 'completed', 'failed')",
            name="ck_export_jobs_status",
        ),
        CheckConstraint(
            "export_type in ('organized_zip', 'metadata_only')",
            name="ck_export_jobs_export_type",
        ),
        CheckConstraint("included_count >= 0", name="ck_export_jobs_included_count"),
        CheckConstraint("excluded_count >= 0", name="ck_export_jobs_excluded_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="created")
    export_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="organized_zip",
    )
    bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    zip_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    included_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    include_duplicates: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    include_blurry: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    include_pending: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    event: Mapped[Event] = relationship(back_populates="export_jobs")
