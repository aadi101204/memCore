"""
Memory service for handling business logic.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import MemoryRecord
from app.models.schemas import (
    MemoryCreate,
    MemoryUpdate,
    MemorySearchResult,
    MemoryResponse,
)
from app.repositories import MemoryRepository

class MemoryService:
    """Service for memory operations."""

    def __init__(self, db: AsyncSession):
        self.repo = MemoryRepository(db)

    async def create_memory(self, memory_data: MemoryCreate) -> MemoryRecord:
        """
        Create a new memory record.
        """
        memory_record = MemoryRecord(
            org_id=memory_data.org_id,
            agent_id=memory_data.agent_id,
            team_id=memory_data.team_id,
            scope=memory_data.scope,
            content=memory_data.content,
            memory_type=memory_data.memory_type,
            confidence=memory_data.confidence,
            source_agent=memory_data.agent_id,
        )
        
        # Set expiration if TTL is provided
        if memory_data.ttl:
            memory_record.expires_at = datetime.utcnow() + timedelta(seconds=memory_data.ttl)
            
        return await self.repo.create(memory_record)

    async def get_memory(self, memory_id: UUID) -> Optional[MemoryRecord]:
        """
        Get a memory by ID and increment usage.
        """
        memory = await self.repo.get_by_id(memory_id)
        if memory:
            await self.repo.increment_usage(memory_id)
        return memory

    async def update_memory(self, memory_id: UUID, memory_update: MemoryUpdate) -> Optional[MemoryRecord]:
        """
        Update a memory record.
        """
        existing = await self.repo.get_by_id(memory_id)
        if not existing:
            return None
            
        # Update fields
        update_data = memory_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)
            
        return await self.repo.update(memory_id, existing)

    async def delete_memory(self, memory_id: UUID) -> bool:
        """
        Soft delete a memory.
        """
        return await self.repo.delete(memory_id)

    async def search_memories(self, search_request) -> List[MemorySearchResult]:
        """
        Search memories using filters.
        """
        # Build filters
        filters = {
            "org_id": search_request.org_id,
            "include_deleted": search_request.include_deleted,
        }
        
        if search_request.agent_id:
            filters["agent_id"] = search_request.agent_id
        
        if search_request.scope:
            filters["scope"] = search_request.scope
        
        if search_request.memory_type:
            filters["memory_type"] = search_request.memory_type
        
        if search_request.min_confidence:
            filters["min_confidence"] = search_request.min_confidence
        
        # Get memories
        memories = await self.repo.get_all(
            skip=0,
            limit=search_request.top_k,
            filters=filters
        )
        
        # TODO: Implement vector search and hybrid ranking
        # For now, just return filtered results
        results = [
            MemorySearchResult(
                memory=MemoryResponse.model_validate(mem),
                score=1.0,  # Placeholder
                semantic_score=1.0,  # Placeholder
                recency_score=1.0,  # Placeholder
            )
            for mem in memories
        ]
        
        return results, len(results)
