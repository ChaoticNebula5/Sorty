"""
RQ queue definitions for Sorty workers.
"""

from redis import Redis
from rq import Queue

from backend.config import settings


def get_redis_connection() -> Redis:
    """Return the sync Redis connection used by RQ."""
    return Redis.from_url(settings.redis_url, decode_responses=False)


def get_enrichment_queue() -> Queue:
    """Return the enrichment queue."""
    return Queue("enrichment", connection=get_redis_connection())


def get_clustering_queue() -> Queue:
    """Return the clustering queue."""
    return Queue("clustering", connection=get_redis_connection())


def get_export_queue() -> Queue:
    """Return the export queue."""
    return Queue("export", connection=get_redis_connection())
