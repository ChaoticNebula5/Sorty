from __future__ import annotations

"""
Asset ORM model.
Represents an uploaded image file with processing metadata.
See PRD §6 (Database Schema) and §7 (Data Models).
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
    Enum as SQLEnum,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base
import enum

if TYPE_CHECKING:
    from backend.models.assistant_run import AssistantRun
    from backend.models.collection import CollectionAsset
    from backend.models.duplicate_cluster import DuplicateClusterMember
    from backend.models.event import Event
    from backend.models.override import Override
    from backend.models.processing_job import ProcessingJob
    from backend.models.asset_metadata import AssetMetadata


class ProcessingStatus(str, enum.Enum):
    """Asset processing status enum (PRD §6)."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


ENUM_VALUES = lambda enum_cls: [member.value for member in enum_cls]  # noqa: E731


class Asset(Base):
    __tablename__ = "assets"

    # Table-level constraints
    __table_args__ = (
        UniqueConstraint("event_id", "file_hash", name="uq_asset_event_hash"),
        Index("idx_assets_event_id", "event_id"),
        Index("idx_assets_processing_status", "processing_status"),
        Index("idx_assets_file_hash", "file_hash"),
    )

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )

    # Foreign keys
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )

    # File metadata
    filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)

    # Image dimensions
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # File size
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    # Processing state
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        SQLEnum(
            ProcessingStatus,
            name="processing_status",
            values_callable=ENUM_VALUES,
            validate_strings=True,
        ),
        nullable=False,
        default=ProcessingStatus.PENDING,
        server_default=text("'pending'"),
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships (string references to avoid circular imports)
    event: Mapped["Event"] = relationship("Event", back_populates="assets")

    asset_metadata: Mapped["AssetMetadata | None"] = relationship(
        "AssetMetadata",
        back_populates="asset",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(
        "ProcessingJob",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    overrides: Mapped[list["Override"]] = relationship(
        "Override",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    cluster_memberships: Mapped[list["DuplicateClusterMember"]] = relationship(
        "DuplicateClusterMember",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    collection_associations: Mapped[list["CollectionAsset"]] = relationship(
        "CollectionAsset",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def url(self) -> str:
        from backend.storage import get_storage

        return get_storage().get_url(self.storage_key)

    @property
    def thumbnail_url(self) -> str:
        from backend.storage import get_storage

        return get_storage().get_url(get_storage().get_thumbnail_key(self.storage_key))

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, filename={self.filename!r}, status={self.processing_status.value})>"
