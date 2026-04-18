"""
Processing service layer.
Handles asset reprocessing and manual event clustering job enqueueing.
"""

from uuid import UUID

from redis import Redis
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Asset, Event, JobStatus, JobType, ProcessingJob
from backend.schemas.asset import (
    ClusterResponse,
    ClusterResponseData,
    ReprocessResponse,
    ReprocessResponseData,
)


class ProcessingService:
    """Business logic for processing and clustering operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis = Redis.from_url(settings.redis_url, decode_responses=False)
        self.enrichment_queue = Queue("enrichment", connection=self.redis)
        self.clustering_queue = Queue("clustering", connection=self.redis)

    async def reprocess_asset(self, asset_id: UUID) -> ReprocessResponse | None:
        """Requeue a failed asset for enrichment."""
        asset = await self.db.get(Asset, asset_id)
        if asset is None:
            return None

        asset.processing_status = "pending"
        asset.error_message = None

        job = ProcessingJob(
            asset_id=asset.id,
            job_type=JobType.METADATA_ENRICHMENT,
            status=JobStatus.QUEUED,
            retry_count=0,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        self.enrichment_queue.enqueue(
            "backend.workers.tasks.enrich_asset.run",
            asset_id=str(asset.id),
            job_id=str(job.id),
        )

        return ReprocessResponse(
            data=ReprocessResponseData(
                job_id=job.id,
                status=job.status.value,
            )
        )

    async def enqueue_event_clustering(self, event_id: UUID) -> ClusterResponse | None:
        """Enqueue duplicate clustering for an event if no lock is held."""
        event = await self.db.get(Event, event_id)
        if event is None:
            return None

        lock_key = f"clustering_lock:{event_id}"
        lock_acquired = self.redis.set(lock_key, b"1", nx=True, ex=600)

        if not lock_acquired:
            return ClusterResponse(data=ClusterResponseData(status="already_running"))

        self.clustering_queue.enqueue(
            "backend.workers.tasks.cluster_event.run",
            event_id=str(event_id),
        )

        return ClusterResponse(data=ClusterResponseData(status="queued"))
