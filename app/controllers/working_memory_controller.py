"""
Working memory controller for session management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
import redis.asyncio as redis

from app.configs.redis import get_redis
from app.decorators import track_metrics
from app.models.schemas import (
    WorkingMemoryUpdate,
    WorkingMemoryResponse,
    SuccessResponse,
)
from app.services.working_memory_service import WorkingMemoryService

router = APIRouter(prefix="/working", tags=["Working Memory"])


@router.put("/{session_id}", response_model=SuccessResponse)
@track_metrics(operation="update_working_memory")
async def update_working_memory(
    session_id: str,
    data: WorkingMemoryUpdate,
    redis_client: redis.Redis = Depends(get_redis)
) -> SuccessResponse:
    """
    Update working memory for a session.
    
    Args:
        session_id: Session identifier
        data: Working memory data
        redis_client: Redis client
    
    Returns:
        Success message
    """
    service = WorkingMemoryService(redis_client)
    
    success = await service.update_working_memory(session_id, data)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update working memory"
        )
    
    return SuccessResponse(message="Working memory updated successfully")


@router.get("/{session_id}", response_model=WorkingMemoryResponse)
@track_metrics(operation="get_working_memory")
async def get_working_memory(
    session_id: str,
    redis_client: redis.Redis = Depends(get_redis)
) -> WorkingMemoryResponse:
    """
    Get working memory for a session.
    
    Args:
        session_id: Session identifier
        redis_client: Redis client
    
    Returns:
        Working memory data
    """
    service = WorkingMemoryService(redis_client)
    
    data, ttl = await service.get_working_memory(session_id)
    
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Working memory for session {session_id} not found"
        )
    
    return WorkingMemoryResponse(
        session_id=session_id,
        data=data,
        ttl=ttl
    )


@router.delete("/{session_id}", response_model=SuccessResponse)
@track_metrics(operation="delete_working_memory")
async def delete_working_memory(
    session_id: str,
    redis_client: redis.Redis = Depends(get_redis)
) -> SuccessResponse:
    """
    Delete working memory for a session.
    
    Args:
        session_id: Session identifier
        redis_client: Redis client
    
    Returns:
        Success message
    """
    service = WorkingMemoryService(redis_client)
    
    success = await service.delete_working_memory(session_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Working memory for session {session_id} not found"
        )
    
    return SuccessResponse(message="Working memory deleted successfully")
