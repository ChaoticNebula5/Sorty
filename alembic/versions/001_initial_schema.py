"""create initial Sorty AI schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(name) >= 2", name="ck_events_name_min_length"),
        sa.UniqueConstraint("slug", name="uq_events_slug"),
    )

    op.create_table(
        "batch_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("langgraph_thread_id", sa.String(length=120), nullable=False),
        sa.Column("current_rq_job_id", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="created",
        ),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "needs_review_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ("
            "'created', 'queued', 'processing', 'waiting_for_review', "
            "'reviewed', 'exporting', 'completed', 'failed', 'partial_failed'"
            ")",
            name="ck_batch_jobs_status",
        ),
        sa.CheckConstraint("total_files >= 0", name="ck_batch_jobs_total_files"),
        sa.CheckConstraint("processed_files >= 0", name="ck_batch_jobs_processed_files"),
        sa.CheckConstraint("failed_files >= 0", name="ck_batch_jobs_failed_files"),
        sa.CheckConstraint(
            "needs_review_count >= 0",
            name="ck_batch_jobs_needs_review_count",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("langgraph_thread_id", name="uq_batch_jobs_thread_id"),
    )

    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("bucket_name", sa.String(length=120), nullable=False),
        sa.Column("original_object_key", sa.Text(), nullable=False),
        sa.Column("thumbnail_object_key", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("file_extension", sa.String(length=12), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "upload_status",
            sa.String(length=40),
            nullable=False,
            server_default="accepted",
        ),
        sa.Column(
            "processing_status",
            sa.String(length=40),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("upload_error", sa.Text(), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "upload_status in ('accepted', 'rejected')",
            name="ck_media_assets_upload_status",
        ),
        sa.CheckConstraint(
            "processing_status in ("
            "'uploaded', 'queued', 'processing', 'processed', "
            "'needs_review', 'failed', 'excluded'"
            ")",
            name="ck_media_assets_processing_status",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_media_assets_size_bytes"),
        sa.CheckConstraint(
            "file_extension in ('.jpg', '.jpeg', '.png', '.webp')",
            name="ck_media_assets_file_extension",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["batch_job_id"],
            ["batch_jobs.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_table(
        "ai_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("primary_subject", sa.String(length=160), nullable=True),
        sa.Column("scene_type", sa.String(length=120), nullable=True),
        sa.Column("people_count", sa.String(length=40), nullable=True),
        sa.Column("event_context", sa.String(length=160), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=False),
        sa.Column("suggested_primary_folder", sa.String(length=120), nullable=True),
        sa.Column("suggested_sub_folder", sa.String(length=120), nullable=True),
        sa.Column("folder_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("folder_reason", sa.Text(), nullable=True),
        sa.Column("model_provider", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(), nullable=True),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(tags) = 'array'",
            name="ck_ai_analyses_tags_array",
        ),
        sa.CheckConstraint(
            "folder_confidence is null or "
            "(folder_confidence >= 0 and folder_confidence <= 1)",
            name="ck_ai_analyses_folder_confidence",
        ),
        sa.CheckConstraint(
            "validation_status in ('valid', 'fallback', 'invalid')",
            name="ck_ai_analyses_validation_status",
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("media_id", name="uq_ai_analyses_media_id"),
    )

    op.create_table(
        "duplicate_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "representative_media_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("hash_algorithm", sa.String(length=40), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("group_size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("threshold >= 0", name="ck_duplicate_groups_threshold"),
        sa.CheckConstraint("group_size >= 2", name="ck_duplicate_groups_group_size"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["batch_job_id"],
            ["batch_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["representative_media_id"],
            ["media_assets.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_table(
        "quality_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blur_score", sa.Numeric(12, 4), nullable=True),
        sa.Column("quality_label", sa.String(length=40), nullable=True),
        sa.Column("perceptual_hash", sa.String(length=32), nullable=True),
        sa.Column("duplicate_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("duplicate_distance", sa.Integer(), nullable=True),
        sa.Column("exif_date_taken", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exif_camera_make", sa.String(length=120), nullable=True),
        sa.Column("exif_camera_model", sa.String(length=120), nullable=True),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("orientation", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quality_label is null or quality_label in "
            "('sharp', 'acceptable', 'blurry')",
            name="ck_quality_signals_quality_label",
        ),
        sa.CheckConstraint(
            "image_width is null or image_width > 0",
            name="ck_quality_signals_image_width",
        ),
        sa.CheckConstraint(
            "image_height is null or image_height > 0",
            name="ck_quality_signals_image_height",
        ),
        sa.CheckConstraint(
            "duplicate_distance is null or duplicate_distance >= 0",
            name="ck_quality_signals_duplicate_distance",
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["duplicate_group_id"],
            ["duplicate_groups.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("media_id", name="uq_quality_signals_media_id"),
    )

    op.create_table(
        "review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("final_primary_folder", sa.String(length=120), nullable=True),
        sa.Column("final_sub_folder", sa.String(length=120), nullable=True),
        sa.Column("final_tags", postgresql.JSONB(), nullable=False),
        sa.Column(
            "include_in_export",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("review_reasons", postgresql.JSONB(), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('pending', 'approved', 'edited', 'rejected', 'duplicate')",
            name="ck_review_decisions_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(final_tags) = 'array'",
            name="ck_review_decisions_final_tags_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(review_reasons) = 'array'",
            name="ck_review_decisions_review_reasons_array",
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("media_id", name="uq_review_decisions_media_id"),
    )

    op.create_table(
        "media_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("indexed_text", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("media_id", name="uq_media_embeddings_media_id"),
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="created",
        ),
        sa.Column(
            "export_type",
            sa.String(length=40),
            nullable=False,
            server_default="organized_zip",
        ),
        sa.Column("bucket_name", sa.String(length=120), nullable=False),
        sa.Column("zip_object_key", sa.Text(), nullable=True),
        sa.Column("included_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("excluded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "include_duplicates",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "include_blurry",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "include_pending",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('created', 'queued', 'exporting', 'completed', 'failed')",
            name="ck_export_jobs_status",
        ),
        sa.CheckConstraint(
            "export_type in ('organized_zip', 'metadata_only')",
            name="ck_export_jobs_export_type",
        ),
        sa.CheckConstraint("included_count >= 0", name="ck_export_jobs_included_count"),
        sa.CheckConstraint("excluded_count >= 0", name="ck_export_jobs_excluded_count"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
    )

    op.create_index("idx_events_created_at", "events", ["created_at"])
    op.create_index("idx_events_event_type", "events", ["event_type"])
    op.create_index("idx_batch_jobs_event_id", "batch_jobs", ["event_id"])
    op.create_index("idx_batch_jobs_status", "batch_jobs", ["status"])
    op.create_index("idx_batch_jobs_created_at", "batch_jobs", ["created_at"])
    op.create_index("idx_media_assets_event_id", "media_assets", ["event_id"])
    op.create_index("idx_media_assets_batch_job_id", "media_assets", ["batch_job_id"])
    op.create_index(
        "idx_media_assets_processing_status",
        "media_assets",
        ["processing_status"],
    )
    op.create_index("idx_media_assets_sha256_hash", "media_assets", ["sha256_hash"])
    op.create_index("idx_media_assets_created_at", "media_assets", ["created_at"])
    op.create_index("idx_ai_analyses_scene_type", "ai_analyses", ["scene_type"])
    op.create_index(
        "idx_ai_analyses_model_provider",
        "ai_analyses",
        ["model_provider"],
    )
    op.create_index(
        "idx_ai_analyses_tags_gin",
        "ai_analyses",
        ["tags"],
        postgresql_using="gin",
    )
    op.create_index("idx_duplicate_groups_event_id", "duplicate_groups", ["event_id"])
    op.create_index(
        "idx_duplicate_groups_batch_job_id",
        "duplicate_groups",
        ["batch_job_id"],
    )
    op.create_index(
        "idx_quality_signals_quality_label",
        "quality_signals",
        ["quality_label"],
    )
    op.create_index(
        "idx_quality_signals_duplicate_group_id",
        "quality_signals",
        ["duplicate_group_id"],
    )
    op.create_index(
        "idx_quality_signals_is_duplicate",
        "quality_signals",
        ["is_duplicate"],
    )
    op.create_index(
        "idx_quality_signals_perceptual_hash",
        "quality_signals",
        ["perceptual_hash"],
    )
    op.create_index("idx_review_decisions_status", "review_decisions", ["status"])
    op.create_index(
        "idx_review_decisions_include_in_export",
        "review_decisions",
        ["include_in_export"],
    )
    op.create_index(
        "idx_review_decisions_reasons_gin",
        "review_decisions",
        ["review_reasons"],
        postgresql_using="gin",
    )
    op.create_index("idx_export_jobs_event_id", "export_jobs", ["event_id"])
    op.create_index("idx_export_jobs_status", "export_jobs", ["status"])
    op.create_index("idx_export_jobs_created_at", "export_jobs", ["created_at"])
    op.create_index(
        "idx_media_embeddings_embedding_ivfflat",
        "media_embeddings",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"lists": 100},
    )


def downgrade() -> None:
    op.drop_index("idx_media_embeddings_embedding_ivfflat", table_name="media_embeddings")
    op.drop_index("idx_export_jobs_created_at", table_name="export_jobs")
    op.drop_index("idx_export_jobs_status", table_name="export_jobs")
    op.drop_index("idx_export_jobs_event_id", table_name="export_jobs")
    op.drop_index("idx_review_decisions_reasons_gin", table_name="review_decisions")
    op.drop_index(
        "idx_review_decisions_include_in_export",
        table_name="review_decisions",
    )
    op.drop_index("idx_review_decisions_status", table_name="review_decisions")
    op.drop_index("idx_quality_signals_perceptual_hash", table_name="quality_signals")
    op.drop_index("idx_quality_signals_is_duplicate", table_name="quality_signals")
    op.drop_index(
        "idx_quality_signals_duplicate_group_id",
        table_name="quality_signals",
    )
    op.drop_index("idx_quality_signals_quality_label", table_name="quality_signals")
    op.drop_index("idx_duplicate_groups_batch_job_id", table_name="duplicate_groups")
    op.drop_index("idx_duplicate_groups_event_id", table_name="duplicate_groups")
    op.drop_index("idx_ai_analyses_tags_gin", table_name="ai_analyses")
    op.drop_index("idx_ai_analyses_model_provider", table_name="ai_analyses")
    op.drop_index("idx_ai_analyses_scene_type", table_name="ai_analyses")
    op.drop_index("idx_media_assets_created_at", table_name="media_assets")
    op.drop_index("idx_media_assets_sha256_hash", table_name="media_assets")
    op.drop_index("idx_media_assets_processing_status", table_name="media_assets")
    op.drop_index("idx_media_assets_batch_job_id", table_name="media_assets")
    op.drop_index("idx_media_assets_event_id", table_name="media_assets")
    op.drop_index("idx_batch_jobs_created_at", table_name="batch_jobs")
    op.drop_index("idx_batch_jobs_status", table_name="batch_jobs")
    op.drop_index("idx_batch_jobs_event_id", table_name="batch_jobs")
    op.drop_index("idx_events_event_type", table_name="events")
    op.drop_index("idx_events_created_at", table_name="events")

    op.drop_table("export_jobs")
    op.drop_table("media_embeddings")
    op.drop_table("review_decisions")
    op.drop_table("quality_signals")
    op.drop_table("duplicate_groups")
    op.drop_table("ai_analyses")
    op.drop_table("media_assets")
    op.drop_table("batch_jobs")
    op.drop_table("events")
