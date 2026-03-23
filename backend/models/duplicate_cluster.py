"""
DuplicateCluster ORM models.
Manages duplicate/near-duplicate image clustering.
See PRD §6 (Database Schema) and §7 (Data Models).
"""

from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, Float, SmallInteger, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class DuplicateCluster(Base):
    __tablename__ = "duplicate_clusters"

    # Table-level indexes
    __table_args__ = (Index("idx_dup_clusters_event_id", "event_id"),)

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )

    # Foreign keys
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )

    representative_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id"), nullable=False
    )

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="duplicate_clusters")

    representative_asset: Mapped["Asset"] = relationship(
        "Asset", foreign_keys=[representative_asset_id]
    )

    members: Mapped[list["DuplicateClusterMember"]] = relationship(
        "DuplicateClusterMember",
        back_populates="cluster",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DuplicateCluster(id={self.id}, representative={self.representative_asset_id})>"


class DuplicateClusterMember(Base):
    __tablename__ = "duplicate_cluster_members"

    # Table-level indexes
    __table_args__ = (Index("idx_dup_members_asset_id", "asset_id"),)

    # Composite primary key
    cluster_id: Mapped[UUID] = mapped_column(
        ForeignKey("duplicate_clusters.id", ondelete="CASCADE"), primary_key=True
    )

    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )

    # Member metadata
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Relationships
    cluster: Mapped["DuplicateCluster"] = relationship(
        "DuplicateCluster", back_populates="members"
    )

    asset: Mapped["Asset"] = relationship("Asset", back_populates="cluster_memberships")

    def __repr__(self) -> str:
        return f"<DuplicateClusterMember(cluster={self.cluster_id}, asset={self.asset_id}, rank={self.rank})>"
