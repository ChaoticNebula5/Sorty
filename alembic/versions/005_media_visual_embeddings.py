"""Add media visual embeddings.

Revision ID: 005_media_visual_embeddings
Revises: 004_public_event_fields
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "005_media_visual_embeddings"
down_revision: str | None = "004_public_event_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_visual_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", Vector(512), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("media_id", name="uq_media_visual_embeddings_media_id"),
    )
    op.create_index(
        "idx_media_visual_embeddings_embedding_ivfflat",
        "media_visual_embeddings",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index(
        "idx_media_visual_embeddings_embedding_ivfflat",
        table_name="media_visual_embeddings",
    )
    op.drop_table("media_visual_embeddings")
