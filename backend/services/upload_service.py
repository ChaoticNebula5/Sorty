"""
Upload service layer.
Handles image upload, duplicate detection, asset creation, and job enqueueing.
"""

import hashlib
from io import BytesIO
from uuid import UUID

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import (
    Asset,
    Event,
    JobStatus,
    JobType,
    ProcessingJob,
    ProcessingStatus,
)
from backend.storage import get_storage


ACCEPTED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}


class UploadService:
    """Business logic for asset uploads."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage()
        self.redis = Redis.from_url(settings.redis_url, decode_responses=False)
        self.enrichment_queue = Queue("enrichment", connection=self.redis)

    async def upload_assets(
        self, event_id: UUID, files: list[UploadFile]
    ) -> dict[str, int | list[dict[str, str | UUID]]]:
        """Upload image files for an event and enqueue enrichment jobs."""
        event = await self.db.get(Event, event_id)
        if event is None:
            raise ValueError("Event not found")

        if len(files) > settings.max_files_per_upload:
            raise ValueError(
                f"Maximum {settings.max_files_per_upload} files allowed per upload"
            )

        uploaded_assets: list[dict[str, str | UUID]] = []
        jobs_to_enqueue: list[tuple[str, str]] = []
        uploaded_count = 0
        skipped_duplicates = 0
        rejected_invalid = 0

        for file in files:
            if file.content_type not in ACCEPTED_MIME_TYPES:
                rejected_invalid += 1
                continue

            file_bytes = await file.read()
            if len(file_bytes) > settings.max_file_size_bytes:
                rejected_invalid += 1
                continue

            if not self._is_valid_image(file_bytes):
                rejected_invalid += 1
                continue

            file_hash = hashlib.sha256(file_bytes).hexdigest()

            duplicate_stmt = select(Asset.id).where(
                Asset.event_id == event_id,
                Asset.file_hash == file_hash,
            )
            duplicate_result = await self.db.execute(duplicate_stmt)
            if duplicate_result.scalar_one_or_none() is not None:
                skipped_duplicates += 1
                continue

            extension = ACCEPTED_MIME_TYPES[file.content_type]
            storage_key = await self.storage.put(file_bytes, file_hash, extension)
            width, height = self._get_image_dimensions(file_bytes)

            try:
                async with self.db.begin_nested():
                    asset = Asset(
                        event_id=event_id,
                        filename=file.filename or f"{file_hash}{extension}",
                        storage_key=storage_key,
                        file_hash=file_hash,
                        mime_type=file.content_type,
                        width=width,
                        height=height,
                        file_size=len(file_bytes),
                    )
                    self.db.add(asset)
                    await self.db.flush()

                    job = ProcessingJob(
                        asset_id=asset.id,
                        job_type=JobType.METADATA_ENRICHMENT,
                    )
                    self.db.add(job)
                    await self.db.flush()
            except IntegrityError:
                await self.storage.delete(storage_key)
                skipped_duplicates += 1
                continue

            jobs_to_enqueue.append((str(asset.id), str(job.id)))

            uploaded_assets.append(
                {
                    "id": asset.id,
                    "filename": asset.filename,
                    "processing_status": asset.processing_status.value,
                }
            )
            uploaded_count += 1

        await self.db.commit()

        for asset_id, job_id in jobs_to_enqueue:
            try:
                self.enrichment_queue.enqueue(
                    "backend.workers.tasks.enrich_asset.run",
                    asset_id,
                    job_id,
                )
            except Exception as exc:
                asset = await self.db.get(Asset, UUID(asset_id))
                job = await self.db.get(ProcessingJob, UUID(job_id))
                if asset is not None:
                    asset.processing_status = ProcessingStatus.FAILED
                    asset.error_message = f"Enrichment enqueue failed: {exc}"
                if job is not None:
                    job.status = JobStatus.FAILED
                    job.error_message = f"Enrichment enqueue failed: {exc}"
                await self.db.commit()

        return {
            "uploaded": uploaded_count,
            "skipped_duplicates": skipped_duplicates,
            "rejected_invalid": rejected_invalid,
            "assets": uploaded_assets,
        }

    @staticmethod
    def _is_valid_image(file_bytes: bytes) -> bool:
        """Check that the uploaded bytes are a readable image."""
        try:
            with Image.open(BytesIO(file_bytes)) as image:
                image.verify()
            return True
        except (UnidentifiedImageError, OSError):
            return False

    @staticmethod
    def _get_image_dimensions(file_bytes: bytes) -> tuple[int | None, int | None]:
        """Extract image width and height."""
        try:
            with Image.open(BytesIO(file_bytes)) as image:
                return image.width, image.height
        except (UnidentifiedImageError, OSError):
            return None, None
