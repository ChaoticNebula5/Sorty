"""
Per-asset enrichment worker task.
Loads an asset, generates enrichment outputs, stores metadata, and updates job status.
"""

import asyncio
from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

from PIL import Image
from sqlalchemy import select

from backend.ai.captioner import get_captioner
from backend.ai.embedder import get_embedder
from backend.ai.quality import get_quality_scorer
from backend.ai.sponsor import get_sponsor_scorer
from backend.database import AsyncSessionLocal
from backend.models import (
    Asset,
    AssetMetadata,
    JobStatus,
    ProcessingJob,
    ProcessingStatus,
)
from backend.storage import get_storage


THUMBNAIL_MAX_DIMENSION = 400
THUMBNAIL_JPEG_QUALITY = 80


def run(asset_id: str, job_id: str) -> None:
    """RQ entrypoint for enriching a single asset."""
    asyncio.run(_run(UUID(asset_id), UUID(job_id)))


async def _run(asset_id: UUID, job_id: UUID) -> None:
    """Execute enrichment pipeline for a single asset."""
    async with AsyncSessionLocal() as db:
        job = await db.get(ProcessingJob, job_id)
        asset = await db.get(Asset, asset_id)

        if job is None or asset is None:
            return

        try:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            asset.processing_status = ProcessingStatus.PROCESSING
            asset.error_message = None
            await db.commit()

            storage = get_storage()
            image_bytes = await storage.get(asset.storage_key)

            thumbnail_bytes = _build_thumbnail(image_bytes)
            await storage.put_thumbnail(thumbnail_bytes, asset.file_hash)

            caption_result = get_captioner().caption_image_bytes(
                image_bytes=image_bytes,
                mime_type=asset.mime_type,
            )
            embedding_vector = get_embedder().embed_image_bytes(image_bytes)
            quality_result = get_quality_scorer().score_image_bytes(image_bytes)
            sponsor_result = get_sponsor_scorer().score_caption_result(caption_result)

            metadata_stmt = select(AssetMetadata).where(
                AssetMetadata.asset_id == asset.id
            )
            metadata_result = await db.execute(metadata_stmt)
            metadata = metadata_result.scalar_one_or_none()

            if metadata is None:
                metadata = AssetMetadata(asset_id=asset.id)
                db.add(metadata)

            metadata.caption = caption_result.get("caption")
            metadata.tags_json = caption_result.get("tags", [])
            metadata.primary_category = caption_result.get("primary_category")
            metadata.category_scores_json = caption_result.get("category_scores", {})
            metadata.embedding_vector = embedding_vector
            metadata.usefulness_score = quality_result["usefulness_score"]
            metadata.blur_score = quality_result["blur_score"]
            metadata.brightness_score = quality_result["brightness_score"]
            metadata.sponsor_visible_score = sponsor_result["sponsor_visible_score"]
            metadata.low_quality_flag = quality_result["low_quality_flag"]

            asset.processing_status = ProcessingStatus.COMPLETED
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as exc:
            await db.rollback()

            job = await db.get(ProcessingJob, job_id)
            asset = await db.get(Asset, asset_id)

            if job is not None:
                job.status = JobStatus.FAILED
                job.error_message = str(exc)
                job.completed_at = datetime.now(timezone.utc)

            if asset is not None:
                asset.processing_status = ProcessingStatus.FAILED
                asset.error_message = str(exc)

            await db.commit()
            raise


def _build_thumbnail(image_bytes: bytes) -> bytes:
    """Generate a max-400px JPEG thumbnail."""
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION))

    output = BytesIO()
    image.save(output, format="JPEG", quality=THUMBNAIL_JPEG_QUALITY)
    return output.getvalue()
