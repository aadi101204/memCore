"""
Memory service interface.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from app.models.schemas import (
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResponse,
)


class IMemoryService(ABC):
    """Memory service interface."""
    
    @abstractmethod
    async def create_memory(self, memory: MemoryCreate) -> MemoryResponse:
        """Create a new memory."""
        pass
    
    @abstractmethod
    async def get_memory(self, memory_id: UUID) -> Optional[MemoryResponse]:
        """Get memory by ID."""
        pass
    
    @abstractmethod
    async def update_memory(
        self, 
        memory_id: UUID, 
        memory_update: MemoryUpdate
    ) -> Optional[MemoryResponse]:
        """Update a memory."""
        pass
    
    @abstractmethod
    async def delete_memory(self, memory_id: UUID) -> bool:
        """Delete a memory (soft delete)."""
        pass
    
    @abstractmethod
    async def search_memories(
        self, 
        search_request: MemorySearchRequest
    ) -> MemorySearchResponse:
        """Search memories using hybrid retrieval."""
        pass
    
    @abstractmethod
    async def increment_usage(self, memory_id: UUID) -> bool:
        """Increment usage count for a memory."""
        pass
