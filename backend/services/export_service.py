"""
Export service layer.
Handles export size validation, export job creation, and export status lookup.
"""

from uuid import UUID

from redis import Redis
from rq import Queue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Asset, Collection, CollectionAsset, ExportJob, ExportStatus
from backend.services.effective_asset_state import (
    effective_hidden_expr,
    effective_low_quality_flag_expr,
)
from backend.schemas.export import (
    ExportResponse,
    ExportResponseData,
    ExportStatusResponse,
    ExportStatusResponseData,
)


class ExportService:
    """Business logic for export operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis = Redis.from_url(settings.redis_url, decode_responses=False)
        self.export_queue = Queue("export", connection=self.redis)

    async def create_export(self, collection_id: UUID) -> ExportResponse:
        """Create an export job after validating estimated size."""
        collection = await self.db.get(Collection, collection_id)
        if collection is None:
            raise ValueError("Collection not found")

        effective_hidden = effective_hidden_expr()
        effective_low_quality = effective_low_quality_flag_expr()
        size_stmt = (
            select(func.coalesce(func.sum(Asset.file_size), 0), func.count(Asset.id))
            .select_from(CollectionAsset)
            .join(Asset, Asset.id == CollectionAsset.asset_id)
            .join(Asset.asset_metadata)
            .where(
                CollectionAsset.collection_id == collection_id,
                effective_hidden.is_(False),
                effective_low_quality.is_(False),
            )
        )
        size_result = await self.db.execute(size_stmt)
        estimated_size_bytes, asset_count = size_result.one()

        if estimated_size_bytes > settings.export_max_size_bytes:
            raise ValueError(
                f"Estimated export size exceeds limit of {settings.export_max_size_bytes} bytes"
            )

        export_job = ExportJob(collection_id=collection_id)
        self.db.add(export_job)
        await self.db.commit()
        await self.db.refresh(export_job)

        try:
            self.export_queue.enqueue(
                "backend.workers.tasks.generate_export.run",
                str(export_job.id),
            )
        except Exception as exc:
            export_job.status = ExportStatus.FAILED
            export_job.error_message = f"Export enqueue failed: {exc}"
            await self.db.commit()
            raise RuntimeError("Export enqueue failed") from exc

        return ExportResponse(
            data=ExportResponseData(
                export_id=export_job.id,
                status=export_job.status.value,
                estimated_size_bytes=estimated_size_bytes,
                asset_count=asset_count,
            )
        )

    async def get_export_status(self, export_id: UUID) -> ExportStatusResponse | None:
        """Return export job status for polling."""
        export_job = await self.db.get(ExportJob, export_id)
        if export_job is None:
            return None

        return ExportStatusResponse(
            data=ExportStatusResponseData(
                export_id=export_job.id,
                status=export_job.status.value,
                download_url=export_job.download_url,
                expires_at=export_job.expires_at,
                size_bytes=export_job.size_bytes,
            )
        )
