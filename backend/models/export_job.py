from __future__ import annotations

"""
ExportJob ORM model.
Tracks export generation state, file location, size, and expiry.
"""

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.collection import Collection


class ExportStatus(str, enum.Enum):
    """Export job status."""

    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


ENUM_VALUES = lambda enum_cls: [member.value for member in enum_cls]  # noqa: E731


class ExportJob(Base):
    __tablename__ = "export_jobs"

    __table_args__ = (
        Index("idx_export_jobs_collection_id", "collection_id"),
        Index("idx_export_jobs_status", "status"),
        Index("idx_export_jobs_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[ExportStatus] = mapped_column(
        SQLEnum(
            ExportStatus,
            name="export_status",
            values_callable=ENUM_VALUES,
            validate_strings=True,
        ),
        nullable=False,
        default=ExportStatus.GENERATING,
        server_default=text("'generating'"),
    )

    storage_key: Mapped[str | None] = mapped_column(String, nullable=True)
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    collection: Mapped["Collection"] = relationship(
        "Collection", back_populates="export_jobs"
    )

    def __repr__(self) -> str:
        return f"<ExportJob(id={self.id}, status={self.status.value})>"
