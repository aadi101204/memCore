"""Redis configuration and connection management."""
from typing import AsyncGenerator

import redis.asyncio as redis

from app.configs.settings import settings

# Create Redis connection pool
redis_pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    max_connections=settings.redis_max_connections,
    decode_responses=True,
)


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """
    Dependency for getting Redis client.
    
    Yields:
        redis.Redis: Redis client
    """
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.close()


async def get_redis_client() -> redis.Redis:
    """
    Get a Redis client instance.
    
    Returns:
        redis.Redis: Redis client
    """
    return redis.Redis(connection_pool=redis_pool)
