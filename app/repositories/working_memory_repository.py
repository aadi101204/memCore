"""
Working memory repository using Redis.
"""
import json
from typing import Optional, Dict, Any

import redis.asyncio as redis

from app.configs.settings import settings


class WorkingMemoryRepository:
    """Repository for working memory using Redis."""
    
    def __init__(self, redis_client: redis.Redis):
        """Initialize repository with Redis client."""
        self.redis = redis_client
        self.prefix = "working_memory:"
    
    def _get_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{self.prefix}{session_id}"
    
    async def set(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set working memory for a session."""
        key = self._get_key(session_id)
        value = json.dumps(data)
        
        if ttl:
            return await self.redis.setex(key, ttl, value)
        else:
            return await self.redis.set(key, value)
    
    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get working memory for a session."""
        key = self._get_key(session_id)
        value = await self.redis.get(key)
        
        if value:
            return json.loads(value)
        return None
    
    async def delete(self, session_id: str) -> bool:
        """Delete working memory for a session."""
        key = self._get_key(session_id)
        result = await self.redis.delete(key)
        return result > 0
    
    async def exists(self, session_id: str) -> bool:
        """Check if working memory exists for a session."""
        key = self._get_key(session_id)
        return await self.redis.exists(key) > 0
    
    async def get_ttl(self, session_id: str) -> Optional[int]:
        """Get remaining TTL for a session."""
        key = self._get_key(session_id)
        ttl = await self.redis.ttl(key)
        return ttl if ttl > 0 else None
    
    async def update_ttl(self, session_id: str, ttl: int) -> bool:
        """Update TTL for a session."""
        key = self._get_key(session_id)
        return await self.redis.expire(key, ttl)
    
    async def append(
        self,
        session_id: str,
        key: str,
        value: Any
    ) -> bool:
        """Append value to a list in working memory."""
        data = await self.get(session_id)
        if not data:
            data = {}
        
        if key not in data:
            data[key] = []
        
        if isinstance(data[key], list):
            data[key].append(value)
            return await self.set(session_id, data)
        
        return False
    
    async def get_all_sessions(self) -> list[str]:
        """Get all active session IDs."""
        pattern = f"{self.prefix}*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            session_id = key.replace(self.prefix, "")
            keys.append(session_id)
        return keys
