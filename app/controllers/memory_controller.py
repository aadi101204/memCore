"""
Memory controller for handling HTTP requests.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.database import get_db
from app.decorators import track_metrics
from app.models.schemas import (
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchRequest,
    MemorySearchResponse,
    SuccessResponse,
)
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
@track_metrics(operation="create_memory")
async def create_memory(
    memory: MemoryCreate,
    db: AsyncSession = Depends(get_db)
) -> MemoryResponse:
    """
    Create a new memory record.
    
    args:
        memory: Memory creation data
        db: Database session
    
    Returns:
        Created memory record
    """
    service = MemoryService(db)
    created_memory = await service.create_memory(memory)
    
    return MemoryResponse.model_validate(created_memory)


@router.get("/{memory_id}", response_model=MemoryResponse)
@track_metrics(operation="get_memory")
async def get_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> MemoryResponse:
    """
    Get a memory by ID.
    
    Args:
        memory_id: Memory ID
        db: Database session
    
    Returns:
        Memory record
    """
    service = MemoryService(db)
    memory = await service.get_memory(memory_id)
    
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with ID {memory_id} not found"
        )
    
    return MemoryResponse.model_validate(memory)


@router.put("/{memory_id}", response_model=MemoryResponse)
@track_metrics(operation="update_memory")
async def update_memory(
    memory_id: UUID,
    memory_update: MemoryUpdate,
    db: AsyncSession = Depends(get_db)
) -> MemoryResponse:
    """
    Update a memory record.
    
    Args:
        memory_id: Memory ID
        memory_update: Update data
        db: Database session
    
    Returns:
        Updated memory record
    """
    service = MemoryService(db)
    updated = await service.update_memory(memory_id, memory_update)
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with ID {memory_id} not found"
        )
    
    return MemoryResponse.model_validate(updated)


@router.delete("/{memory_id}", response_model=SuccessResponse)
@track_metrics(operation="delete_memory")
async def delete_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> SuccessResponse:
    """
    Delete a memory (soft delete).
    
    Args:
        memory_id: Memory ID
        db: Database session
    
    Returns:
        Success message
    """
    service = MemoryService(db)
    success = await service.delete_memory(memory_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with ID {memory_id} not found"
        )
    
    return SuccessResponse(message="Memory deleted successfully")


@router.post("/search", response_model=MemorySearchResponse)
@track_metrics(operation="search_memories")
async def search_memories(
    search_request: MemorySearchRequest,
    db: AsyncSession = Depends(get_db)
) -> MemorySearchResponse:
    """
    Search memories using filters.
    
    Args:
        search_request: Search parameters
        db: Database session
    
    Returns:
        Search results
    """
    service = MemoryService(db)
    results, total = await service.search_memories(search_request)
    
    return MemorySearchResponse(
        results=results,
        total=total,
        query=search_request.query
    )
