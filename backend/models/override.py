"""
Override ORM model.
Stores user corrections to AI-generated metadata.
See PRD §6 (Database Schema) and §7 (Data Models).
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, Text, DateTime, Index, Enum as SQLEnum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base
import enum


class OverrideType(str, enum.Enum):
    """Override type enum (PRD §6)."""

    HIDE = "hide"
    PIN = "pin"
    TAG_OVERRIDE = "tag_override"
    CAPTION_OVERRIDE = "caption_override"
    SPONSOR_VISIBLE_OVERRIDE = "sponsor_visible_override"
    USEFUL_OVERRIDE = "useful_override"


class Override(Base):
    __tablename__ = "overrides"

    # Table-level indexes
    __table_args__ = (Index("idx_overrides_asset_id", "asset_id"),)

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )

    # Foreign keys
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )

    # Override data
    type: Mapped[OverrideType] = mapped_column(
        SQLEnum(OverrideType, name="override_type"), nullable=False
    )

    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    # Relationships
    asset: Mapped["Asset"] = relationship("Asset", back_populates="overrides")

    def __repr__(self) -> str:
        return (
            f"<Override(id={self.id}, type={self.type.value}, asset={self.asset_id})>"
        )
