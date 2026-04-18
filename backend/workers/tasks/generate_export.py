"""
Export generation worker task.
Builds a ZIP archive for a collection and updates export job state.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import Asset, CollectionAsset, ExportJob, ExportStatus
from backend.storage import get_storage


def run(export_id: str) -> None:
    """RQ entrypoint for generating an export ZIP."""
    asyncio.run(_run(UUID(export_id)))


async def _run(export_id: UUID) -> None:
    """Generate the export archive and update the export job."""
    async with AsyncSessionLocal() as db:
        export_job = await db.get(ExportJob, export_id)
        if export_job is None:
            return

        try:
            asset_stmt = (
                select(Asset)
                .join(CollectionAsset, CollectionAsset.asset_id == Asset.id)
                .where(CollectionAsset.collection_id == export_job.collection_id)
                .order_by(Asset.uploaded_at.asc())
            )
            asset_result = await db.execute(asset_stmt)
            assets = asset_result.scalars().all()

            export_dir = Path(settings.export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)

            archive_path = export_dir / f"{export_job.id}.zip"
            storage = get_storage()

            with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
                for asset in assets:
                    file_bytes = await storage.get(asset.storage_key)
                    archive.writestr(asset.filename, file_bytes)

            export_job.storage_key = str(archive_path)
            export_job.download_url = f"/exports/download/{export_job.id}"
            export_job.size_bytes = archive_path.stat().st_size
            export_job.status = ExportStatus.READY
            export_job.expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=settings.export_link_ttl_seconds
            )

            await db.commit()
        except Exception as exc:
            await db.rollback()

            export_job = await db.get(ExportJob, export_id)
            if export_job is not None:
                export_job.status = ExportStatus.FAILED
                export_job.error_message = str(exc)
                await db.commit()

            raise
