from __future__ import annotations

"""
ProcessingJob ORM model.
Tracks background processing jobs for assets with retry logic.
See PRD §6 (Database Schema) and §7 (Data Models).
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import (
    ForeignKey,
    SmallInteger,
    Text,
    DateTime,
    Index,
    Enum as SQLEnum,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base
import enum

if TYPE_CHECKING:
    from backend.models.asset import Asset


class JobType(str, enum.Enum):
    """Job type enum (PRD §6)."""

    METADATA_ENRICHMENT = "metadata_enrichment"
    DUPLICATE_CLUSTERING = "duplicate_clustering"


class JobStatus(str, enum.Enum):
    """Job status enum (PRD §6)."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


ENUM_VALUES = lambda enum_cls: [member.value for member in enum_cls]  # noqa: E731


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    # Table-level indexes
    __table_args__ = (
        Index("idx_jobs_asset_id", "asset_id"),
        Index("idx_jobs_status", "status"),
    )

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )

    # Foreign keys
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )

    # Job metadata
    job_type: Mapped[JobType] = mapped_column(
        SQLEnum(
            JobType,
            name="job_type",
            values_callable=ENUM_VALUES,
            validate_strings=True,
        ),
        nullable=False,
    )

    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(
            JobStatus,
            name="job_status",
            values_callable=ENUM_VALUES,
            validate_strings=True,
        ),
        nullable=False,
        default=JobStatus.QUEUED,
        server_default=text("'queued'"),
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    retry_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default=text("0")
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    asset: Mapped["Asset"] = relationship("Asset", back_populates="processing_jobs")

    def __repr__(self) -> str:
        return f"<ProcessingJob(id={self.id}, type={self.job_type.value}, status={self.status.value})>"
