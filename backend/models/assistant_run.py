from __future__ import annotations

"""
AssistantRun ORM model.
Tracks assistant action execution for audit trail.
See PRD §6 (Database Schema) and §7 (Data Models).
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, DateTime, Index, Enum as SQLEnum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from backend.database import Base
import enum

if TYPE_CHECKING:
    from backend.models.event import Event


class AssistantAction(str, enum.Enum):
    """Assistant action type enum (PRD §6)."""

    CREATE_INSTAGRAM_PACK = "create_instagram_pack"
    FIND_SPONSOR_VISIBLE_MEDIA = "find_sponsor_visible_media"
    SHOW_BEST_STAGE_SHOTS = "show_best_stage_shots"
    BUILD_COLLECTION_FROM_FILTERS = "build_collection_from_filters"


ENUM_VALUES = lambda enum_cls: [member.value for member in enum_cls]  # noqa: E731


class AssistantRun(Base):
    __tablename__ = "assistant_runs"

    # Table-level indexes
    __table_args__ = (Index("idx_assistant_runs_event_id", "event_id"),)

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )

    # Foreign keys
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )

    # Action metadata
    action_type: Mapped[AssistantAction] = mapped_column(
        SQLEnum(
            AssistantAction,
            name="assistant_action",
            values_callable=ENUM_VALUES,
            validate_strings=True,
        ),
        nullable=False,
    )

    input: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="assistant_runs")

    def __repr__(self) -> str:
        return f"<AssistantRun(id={self.id}, action={self.action_type.value})>"
