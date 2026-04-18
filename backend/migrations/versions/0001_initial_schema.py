"""initial schema

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-04-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


processing_status_enum = sa.Enum(
    "pending", "processing", "completed", "failed", name="processing_status"
)
job_type_enum = sa.Enum("metadata_enrichment", "duplicate_clustering", name="job_type")
job_status_enum = sa.Enum(
    "queued", "processing", "completed", "failed", name="job_status"
)
override_type_enum = sa.Enum(
    "hide",
    "pin",
    "tag_override",
    "caption_override",
    "sponsor_visible_override",
    "useful_override",
    name="override_type",
)
assistant_action_enum = sa.Enum(
    "create_instagram_pack",
    "find_sponsor_visible_media",
    "show_best_stage_shots",
    "build_collection_from_filters",
    name="assistant_action",
)
export_status_enum = sa.Enum("generating", "ready", "failed", name="export_status")


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    processing_status_enum.create(op.get_bind(), checkfirst=True)
    job_type_enum.create(op.get_bind(), checkfirst=True)
    job_status_enum.create(op.get_bind(), checkfirst=True)
    override_type_enum.create(op.get_bind(), checkfirst=True)
    assistant_action_enum.create(op.get_bind(), checkfirst=True)
    export_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "assets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "processing_status",
            processing_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "file_hash", name="uq_asset_event_hash"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("idx_assets_event_id", "assets", ["event_id"])
    op.create_index("idx_assets_processing_status", "assets", ["processing_status"])
    op.create_index("idx_assets_file_hash", "assets", ["file_hash"])

    op.create_table(
        "asset_metadata",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column(
            "tags_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("primary_category", sa.Text(), nullable=True),
        sa.Column(
            "category_scores_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("embedding_vector", Vector(512), nullable=True),
        sa.Column("usefulness_score", sa.SmallInteger(), nullable=True),
        sa.Column("blur_score", sa.Float(), nullable=True),
        sa.Column("brightness_score", sa.Float(), nullable=True),
        sa.Column("sponsor_visible_score", sa.Float(), nullable=True),
        sa.Column(
            "duplicate_hidden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "low_quality_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("fts_vector", postgresql.TSVECTOR(), nullable=True),
        sa.CheckConstraint(
            "usefulness_score BETWEEN 0 AND 100", name="ck_usefulness_score_range"
        ),
        sa.CheckConstraint(
            "sponsor_visible_score BETWEEN 0.0 AND 1.0", name="ck_sponsor_score_range"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index(
        "idx_asset_metadata_embedding",
        "asset_metadata",
        ["embedding_vector"],
        unique=False,
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding_vector": "vector_cosine_ops"},
    )
    op.create_index(
        "idx_asset_metadata_fts",
        "asset_metadata",
        ["fts_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_asset_metadata_tags",
        "asset_metadata",
        ["tags_json"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "processing_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", job_type_enum, nullable=False),
        sa.Column(
            "status",
            job_status_enum,
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "retry_count",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_jobs_asset_id", "processing_jobs", ["asset_id"])
    op.create_index("idx_jobs_status", "processing_jobs", ["status"])

    op.create_table(
        "collections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_collections_event_id", "collections", ["event_id"])

    op.create_table(
        "collection_assets",
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("collection_id", "asset_id"),
    )

    op.create_table(
        "duplicate_clusters",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "representative_asset_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["representative_asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_dup_clusters_event_id", "duplicate_clusters", ["event_id"])

    op.create_table(
        "duplicate_cluster_members",
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["cluster_id"], ["duplicate_clusters.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("cluster_id", "asset_id"),
    )
    op.create_index(
        "idx_dup_members_asset_id", "duplicate_cluster_members", ["asset_id"]
    )

    op.create_table(
        "overrides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", override_type_enum, nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_overrides_asset_id", "overrides", ["asset_id"])

    op.create_table(
        "assistant_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", assistant_action_enum, nullable=False),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_assistant_runs_event_id", "assistant_runs", ["event_id"])

    op.create_table(
        "export_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            export_status_enum,
            nullable=False,
            server_default=sa.text("'generating'"),
        ),
        sa.Column("storage_key", sa.String(), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_export_jobs_collection_id", "export_jobs", ["collection_id"])
    op.create_index("idx_export_jobs_status", "export_jobs", ["status"])
    op.create_index("idx_export_jobs_expires_at", "export_jobs", ["expires_at"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_asset_metadata_fts_vector()
        RETURNS trigger AS $$
        BEGIN
            NEW.fts_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.caption, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(ARRAY(SELECT jsonb_array_elements_text(NEW.tags_json)), ' '), '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_asset_metadata_fts_vector
        BEFORE INSERT OR UPDATE OF caption, tags_json ON asset_metadata
        FOR EACH ROW
        EXECUTE FUNCTION update_asset_metadata_fts_vector();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_asset_metadata_fts_vector ON asset_metadata")
    op.execute("DROP FUNCTION IF EXISTS update_asset_metadata_fts_vector")

    op.drop_index("idx_export_jobs_expires_at", table_name="export_jobs")
    op.drop_index("idx_export_jobs_status", table_name="export_jobs")
    op.drop_index("idx_export_jobs_collection_id", table_name="export_jobs")
    op.drop_table("export_jobs")

    op.drop_index("idx_assistant_runs_event_id", table_name="assistant_runs")
    op.drop_table("assistant_runs")

    op.drop_index("idx_overrides_asset_id", table_name="overrides")
    op.drop_table("overrides")

    op.drop_index("idx_dup_members_asset_id", table_name="duplicate_cluster_members")
    op.drop_table("duplicate_cluster_members")

    op.drop_index("idx_dup_clusters_event_id", table_name="duplicate_clusters")
    op.drop_table("duplicate_clusters")

    op.drop_table("collection_assets")

    op.drop_index("idx_collections_event_id", table_name="collections")
    op.drop_table("collections")

    op.drop_index("idx_jobs_status", table_name="processing_jobs")
    op.drop_index("idx_jobs_asset_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")

    op.drop_index("idx_asset_metadata_tags", table_name="asset_metadata")
    op.drop_index("idx_asset_metadata_fts", table_name="asset_metadata")
    op.drop_index("idx_asset_metadata_embedding", table_name="asset_metadata")
    op.drop_table("asset_metadata")

    op.drop_index("idx_assets_file_hash", table_name="assets")
    op.drop_index("idx_assets_processing_status", table_name="assets")
    op.drop_index("idx_assets_event_id", table_name="assets")
    op.drop_table("assets")

    op.drop_table("events")

    export_status_enum.drop(op.get_bind(), checkfirst=True)
    assistant_action_enum.drop(op.get_bind(), checkfirst=True)
    override_type_enum.drop(op.get_bind(), checkfirst=True)
    job_status_enum.drop(op.get_bind(), checkfirst=True)
    job_type_enum.drop(op.get_bind(), checkfirst=True)
    processing_status_enum.drop(op.get_bind(), checkfirst=True)
