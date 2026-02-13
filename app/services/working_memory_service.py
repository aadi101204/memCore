"""
Working memory service for handling session data.
"""
from typing import Optional, Dict, Any, Tuple
import redis.asyncio as redis

from app.models.schemas import WorkingMemoryUpdate
from app.repositories import WorkingMemoryRepository

class WorkingMemoryService:
    """Service for working memory operations."""

    def __init__(self, redis_client: redis.Redis):
        self.repo = WorkingMemoryRepository(redis_client)

    async def update_working_memory(self, session_id: str, data: WorkingMemoryUpdate) -> bool:
        """
        Update working memory for a session.
        """
        return await self.repo.set(
            session_id=session_id,
            data=data.data,
            ttl=data.ttl
        )

    async def get_working_memory(self, session_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
        """
        Get working memory and TTL for a session.
        """
        data = await self.repo.get(session_id)
        if data is None:
            return None, None
            
        ttl = await self.repo.get_ttl(session_id)
        return data, ttl

    async def delete_working_memory(self, session_id: str) -> bool:
        """
        Delete working memory for a session.
        """
        return await self.repo.delete(session_id)
