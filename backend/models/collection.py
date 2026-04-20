"""
Collection ORM models.
Manages user-curated collections of assets for export workflows.
See PRD §6 (Database Schema) and §7 (Data Models).
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, String, DateTime, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.export_job import ExportJob


class Collection(Base):
    __tablename__ = "collections"

    # Table-level indexes
    __table_args__ = (Index("idx_collections_event_id", "event_id"),)

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )

    # Foreign keys
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )

    # Fields
    name: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="collections")

    asset_associations: Mapped[list["CollectionAsset"]] = relationship(
        "CollectionAsset",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    export_jobs: Mapped[list["ExportJob"]] = relationship(
        "ExportJob",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Collection(id={self.id}, name={self.name!r})>"


class CollectionAsset(Base):
    __tablename__ = "collection_assets"

    # Composite primary key
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )

    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )

    # Timestamp
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    # Relationships
    collection: Mapped["Collection"] = relationship(
        "Collection", back_populates="asset_associations"
    )

    asset: Mapped["Asset"] = relationship(
        "Asset", back_populates="collection_associations"
    )

    def __repr__(self) -> str:
        return (
            f"<CollectionAsset(collection={self.collection_id}, asset={self.asset_id})>"
        )
