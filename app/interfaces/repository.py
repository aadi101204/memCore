"""
Abstract repository interface.
All repositories should implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Any
from uuid import UUID

T = TypeVar("T")


class IRepository(ABC, Generic[T]):
    """Base repository interface."""
    
    @abstractmethod
    async def create(self, obj: T) -> T:
        """Create a new record."""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get record by ID."""
        pass
    
    @abstractmethod
    async def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[dict] = None
    ) -> List[T]:
        """Get all records with pagination and filters."""
        pass
    
    @abstractmethod
    async def update(self, id: UUID, obj: T) -> Optional[T]:
        """Update a record."""
        pass
    
    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """Delete a record."""
        pass
    
    @abstractmethod
    async def count(self, filters: Optional[dict] = None) -> int:
        """Count records with optional filters."""
        pass
