"""
Redis connection for queue management and caching.
Uses async Redis client for consistency with async architecture.
"""

from redis.asyncio import Redis
from backend.config import settings

# Async Redis client singleton
redis_client: Redis = Redis.from_url(
    settings.redis_url,
    decode_responses=False,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
)


async def get_redis() -> Redis:
    """
    Get async Redis client instance.
    Returns the global redis_client singleton.
    """
    return redis_client


async def close_redis():
    """Close Redis connection."""
    await redis_client.aclose()
