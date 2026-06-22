"""add public event publishing fields

Revision ID: 004_public_event_fields
Revises: 003_checkpoint_repair
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_public_event_fields"
down_revision: str | None = "003_checkpoint_repair"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "events",
        sa.Column("public_slug", sa.String(length=180), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_events_public_slug", "events", ["public_slug"])


def downgrade() -> None:
    op.drop_constraint("uq_events_public_slug", "events", type_="unique")
    op.drop_column("events", "published_at")
    op.drop_column("events", "public_slug")
    op.drop_column("events", "is_public")
