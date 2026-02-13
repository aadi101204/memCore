"""
Memory repository for database operations.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.interfaces.repository import IRepository
from app.models.memory import MemoryRecord, MemoryScope, MemoryType


class MemoryRepository(IRepository[MemoryRecord]):
    """Repository for memory records."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session
    
    async def create(self, memory: MemoryRecord) -> MemoryRecord:
        """Create a new memory record."""
        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)
        return memory
    
    async def get_by_id(self, id: UUID) -> Optional[MemoryRecord]:
        """Get memory by ID."""
        result = await self.session.execute(
            select(MemoryRecord).where(MemoryRecord.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict] = None
    ) -> List[MemoryRecord]:
        """Get all memories with pagination and filters."""
        query = select(MemoryRecord)
        
        if filters:
            query = self._apply_filters(query, filters)
        
        query = query.offset(skip).limit(limit).order_by(MemoryRecord.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update(self, id: UUID, memory: MemoryRecord) -> Optional[MemoryRecord]:
        """Update memory record."""
        existing = await self.get_by_id(id)
        if not existing:
            return None
        
        for key, value in memory.__dict__.items():
            if not key.startswith("_") and value is not None:
                setattr(existing, key, value)
        
        existing.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(existing)
        return existing
    
    async def delete(self, id: UUID) -> bool:
        """Soft delete memory record."""
        existing = await self.get_by_id(id)
        if not existing:
            return False
        
        existing.is_deleted = True
        existing.deleted_at = datetime.utcnow()
        await self.session.commit()
        return True
    
    async def hard_delete(self, id: UUID) -> bool:
        """Permanently delete memory record."""
        result = await self.session.execute(
            delete(MemoryRecord).where(MemoryRecord.id == id)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def count(self, filters: Optional[dict] = None) -> int:
        """Count memories with optional filters."""
        query = select(func.count(MemoryRecord.id))
        
        if filters:
            query = self._apply_filters(query, filters)
        
        result = await self.session.execute(query)
        return result.scalar_one()
    
    async def get_by_org(
        self,
        org_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[MemoryRecord]:
        """Get memories by organization."""
        result = await self.session.execute(
            select(MemoryRecord)
            .where(MemoryRecord.org_id == org_id)
            .where(MemoryRecord.is_deleted == False)
            .offset(skip)
            .limit(limit)
            .order_by(MemoryRecord.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_by_agent(
        self,
        agent_id: UUID,
        scope: Optional[MemoryScope] = None
    ) -> List[MemoryRecord]:
        """Get memories by agent with optional scope filter."""
        query = select(MemoryRecord).where(
            MemoryRecord.agent_id == agent_id,
            MemoryRecord.is_deleted == False
        )
        
        if scope:
            query = query.where(MemoryRecord.scope == scope)
        
        result = await self.session.execute(query.order_by(MemoryRecord.created_at.desc()))
        return list(result.scalars().all())
    
    async def get_expired_memories(self) -> List[MemoryRecord]:
        """Get all expired memories."""
        now = datetime.utcnow()
        result = await self.session.execute(
            select(MemoryRecord)
            .where(MemoryRecord.expires_at <= now)
            .where(MemoryRecord.is_deleted == False)
        )
        return list(result.scalars().all())
    
    async def get_conflicting_memories(
        self,
        org_id: UUID,
        content_hash: Optional[str] = None
    ) -> List[MemoryRecord]:
        """Get memories marked as conflicts."""
        query = select(MemoryRecord).where(
            MemoryRecord.org_id == org_id,
            MemoryRecord.conflict_flag == True,
            MemoryRecord.is_deleted == False
        )
        
        if content_hash:
            # Add content similarity check if needed
            pass
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def increment_usage(self, id: UUID) -> bool:
        """Increment usage count and update last accessed time."""
        result = await self.session.execute(
            update(MemoryRecord)
            .where(MemoryRecord.id == id)
            .values(
                usage_count=MemoryRecord.usage_count + 1,
                last_accessed_at=datetime.utcnow()
            )
        )
        await self.session.commit()
        return result.rowcount > 0
    
    def _apply_filters(self, query, filters: dict):
        """Apply filters to query."""
        if "org_id" in filters:
            query = query.where(MemoryRecord.org_id == filters["org_id"])
        
        if "agent_id" in filters:
            query = query.where(MemoryRecord.agent_id == filters["agent_id"])
        
        if "scope" in filters:
            query = query.where(MemoryRecord.scope == filters["scope"])
        
        if "memory_type" in filters:
            query = query.where(MemoryRecord.memory_type == filters["memory_type"])
        
        if "include_deleted" not in filters or not filters["include_deleted"]:
            query = query.where(MemoryRecord.is_deleted == False)
        
        if "min_confidence" in filters:
            query = query.where(MemoryRecord.confidence >= filters["min_confidence"])
        
        return query
