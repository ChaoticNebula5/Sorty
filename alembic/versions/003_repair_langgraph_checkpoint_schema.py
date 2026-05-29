"""repair LangGraph checkpoint table schema

Revision ID: 003_checkpoint_repair
Revises: 002_langgraph_checkpoints
Create Date: 2026-05-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "003_checkpoint_repair"
down_revision: str | None = "002_langgraph_checkpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE checkpoint_blobs
        ALTER COLUMN blob DROP NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE checkpoint_writes
        ADD COLUMN IF NOT EXISTS task_path TEXT NOT NULL DEFAULT ''
        """
    )
    op.execute(
        """
        INSERT INTO checkpoint_migrations (v)
        SELECT generate_series(0, 9)
        ON CONFLICT (v) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE checkpoint_writes DROP COLUMN IF EXISTS task_path")
