"""
Memory controller — HTTP endpoints for memory CRUD and semantic search.
All endpoints require authentication via JWT Bearer token or API key.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.database import get_db
from app.decorators import track_metrics
from app.dependencies.auth_dependencies import get_auth_context
from app.models.auth_schemas import AuthContext
from app.models.schemas import (
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
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
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MemoryResponse:
    """
    Create a new memory record.

    The authenticated agent must have access to the target organisation.
    An embedding is generated and stored in Qdrant automatically.
    """
    # Org access check
    if not auth.can_access_org(memory.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to organisation {memory.org_id}",
        )

    service = MemoryService(db)
    created_memory = await service.create_memory(memory)
    return MemoryResponse.model_validate(created_memory)


@router.get("/{memory_id}", response_model=MemoryResponse)
@track_metrics(operation="get_memory")
async def get_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MemoryResponse:
    """
    Get a single memory by ID. Increments its usage counter.
    """
    service = MemoryService(db)
    memory = await service.get_memory(memory_id)

    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    # Verify org access
    if not auth.can_access_org(memory.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this memory",
        )

    return MemoryResponse.model_validate(memory)


@router.put("/{memory_id}", response_model=MemoryResponse)
@track_metrics(operation="update_memory")
async def update_memory(
    memory_id: UUID,
    memory_update: MemoryUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MemoryResponse:
    """
    Update a memory record. If content is changed, the embedding is refreshed.
    """
    service = MemoryService(db)

    # Verify memory exists and check org access before updating
    existing = await service.repo.get_by_id(memory_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    if not auth.can_access_org(existing.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this memory",
        )

    updated = await service.update_memory(memory_id, memory_update)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    return MemoryResponse.model_validate(updated)


@router.delete("/{memory_id}", response_model=SuccessResponse)
@track_metrics(operation="delete_memory")
async def delete_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> SuccessResponse:
    """
    Soft-delete a memory. Removes its vector from Qdrant.
    """
    service = MemoryService(db)

    existing = await service.repo.get_by_id(memory_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    if not auth.can_access_org(existing.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this memory",
        )

    success = await service.delete_memory(memory_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    return SuccessResponse(message="Memory deleted successfully")


@router.post("/search", response_model=MemorySearchResponse)
@track_metrics(operation="search_memories")
async def search_memories(
    search_request: MemorySearchRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MemorySearchResponse:
    """
    Search memories using hybrid ranking (semantic vector search + recency + confidence + usage).

    The query is embedded and matched against Qdrant, results re-ranked by the
    weighted scoring formula, and the top_k returned.
    """
    # Enforce org access for the search target
    if not auth.can_access_org(search_request.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to organisation {search_request.org_id}",
        )

    # If agent_id filter specified, validate access
    if search_request.agent_id and not auth.can_access_agent(search_request.agent_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to agent {search_request.agent_id}",
        )

    service = MemoryService(db)
    results, total = await service.search_memories(search_request)

    return MemorySearchResponse(
        results=results,
        total=total,
        query=search_request.query,
    )
