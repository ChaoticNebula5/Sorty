"""
Maintenance utilities for reconciling legacy or stuck jobs.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models import (
    Asset,
    ExportJob,
    ExportStatus,
    JobStatus,
    JobType,
    ProcessingJob,
    ProcessingStatus,
)
from backend.workers.queues import get_enrichment_queue, get_export_queue


STALE_JOB_MINUTES = 30


def main() -> None:
    """Run reconciliation checks for stuck enrichment/export jobs."""
    asyncio.run(_main())


async def _main() -> None:
    """Mark stale jobs failed and requeue recoverable work."""
    async with AsyncSessionLocal() as db:
        stale_threshold = datetime.now(timezone.utc) - timedelta(
            minutes=STALE_JOB_MINUTES
        )

        processing_stmt = select(ProcessingJob).where(
            ProcessingJob.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]),
            ProcessingJob.created_at < stale_threshold,
        )
        processing_result = await db.execute(processing_stmt)
        stale_jobs = processing_result.scalars().all()

        enrichment_queue = get_enrichment_queue()
        for job in stale_jobs:
            asset = await db.get(Asset, job.asset_id)
            if asset is None:
                continue

            if job.job_type == JobType.METADATA_ENRICHMENT and job.retry_count < 1:
                job.status = JobStatus.QUEUED
                job.error_message = "Reconciled and requeued after stale state"
                asset.processing_status = ProcessingStatus.PENDING
                enrichment_queue.enqueue(
                    "backend.workers.tasks.enrich_asset.run",
                    str(asset.id),
                    str(job.id),
                )
            else:
                job.status = JobStatus.FAILED
                job.error_message = "Marked failed by reconciliation utility"
                asset.processing_status = ProcessingStatus.FAILED
                asset.error_message = job.error_message

        export_stmt = select(ExportJob).where(
            ExportJob.status == ExportStatus.GENERATING,
            ExportJob.created_at < stale_threshold,
        )
        export_result = await db.execute(export_stmt)
        stale_exports = export_result.scalars().all()
        export_queue = get_export_queue()
        for export_job in stale_exports:
            export_job.status = ExportStatus.GENERATING
            export_job.error_message = "Reconciled and requeued after stale state"
            export_queue.enqueue(
                "backend.workers.tasks.generate_export.run",
                str(export_job.id),
            )

        await db.commit()


if __name__ == "__main__":
    main()
