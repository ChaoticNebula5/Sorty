"""
Event ORM model.
Represents a top-level event container for assets.
See PRD §6 (Database Schema) and §7 (Data Models).
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Event(Base):
    __tablename__ = "events"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )

    # Fields
    name: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships (string references to avoid circular imports)
    assets: Mapped[list["Asset"]] = relationship(
        "Asset", back_populates="event", cascade="all, delete-orphan", lazy="selectin"
    )

    collections: Mapped[list["Collection"]] = relationship(
        "Collection",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    duplicate_clusters: Mapped[list["DuplicateCluster"]] = relationship(
        "DuplicateCluster",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    assistant_runs: Mapped[list["AssistantRun"]] = relationship(
        "AssistantRun",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, name={self.name!r})>"
