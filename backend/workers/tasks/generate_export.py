"""
Export generation worker task.
Builds a ZIP archive for a collection and updates export job state.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import AsyncSessionLocal, close_db
from backend.models import Asset, CollectionAsset, ExportJob, ExportStatus
from backend.services.effective_asset_state import (
    asset_response_with_overrides,
    is_effective_low_quality_asset,
    is_hidden_asset,
)
from backend.storage import get_storage


def run(export_id: str) -> None:
    """RQ entrypoint for generating an export ZIP."""
    asyncio.run(_run_with_cleanup(UUID(export_id)))


async def _run_with_cleanup(export_id: UUID) -> None:
    """Run task and dispose DB connections bound to the event loop."""
    try:
        await _run(export_id)
    finally:
        await close_db()


async def _run(export_id: UUID) -> None:
    """Generate the export archive and update the export job."""
    async with AsyncSessionLocal() as db:
        export_job = await db.get(ExportJob, export_id)
        if export_job is None:
            return

        try:
            asset_stmt = (
                select(Asset)
                .options(
                    selectinload(Asset.asset_metadata), selectinload(Asset.overrides)
                )
                .join(CollectionAsset, CollectionAsset.asset_id == Asset.id)
                .where(CollectionAsset.collection_id == export_job.collection_id)
                .order_by(Asset.uploaded_at.asc())
            )
            asset_result = await db.execute(asset_stmt)
            assets = asset_result.scalars().all()
            storage = get_storage()

            export_buffer = BytesIO()
            metadata_rows: list[dict] = []
            used_filenames: set[str] = set()

            with ZipFile(export_buffer, "w", compression=ZIP_DEFLATED) as archive:
                for asset in assets:
                    if is_hidden_asset(asset) or is_effective_low_quality_asset(asset):
                        continue

                    asset_response = asset_response_with_overrides(asset)
                    metadata = asset_response.metadata
                    if metadata is None:
                        continue

                    file_bytes = await storage.get(asset.storage_key)
                    archive_name = _unique_archive_name(
                        asset.filename, asset.id, used_filenames
                    )
                    archive.writestr(archive_name, file_bytes)
                    metadata_rows.append(
                        {
                            "filename": archive_name,
                            "caption": metadata.caption,
                            "tags": metadata.tags,
                            "usefulness_score": metadata.usefulness_score,
                            "primary_category": metadata.primary_category,
                        }
                    )

                archive.writestr(
                    "metadata.json",
                    json.dumps(metadata_rows, indent=2).encode("utf-8"),
                )

            export_bytes = export_buffer.getvalue()
            export_storage_key = await storage.put_bytes(
                export_bytes,
                f"exports/{export_job.id}.zip",
            )

            export_job.storage_key = export_storage_key
            export_job.download_url = f"/api/v1/exports/{export_job.id}/download"
            export_job.size_bytes = len(export_bytes)
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


def _unique_archive_name(
    filename: str, asset_id: UUID, used_filenames: set[str]
) -> str:
    """Return a unique archive member name for the ZIP."""
    candidate = filename
    if candidate not in used_filenames:
        used_filenames.add(candidate)
        return candidate

    unique_name = f"{asset_id}_{filename}"
    used_filenames.add(unique_name)
    return unique_name
