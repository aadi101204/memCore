"""
Conflict resolution controller — endpoints for detecting and resolving memory conflicts.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.database import get_db
from app.decorators import track_metrics
from app.dependencies.auth_dependencies import get_auth_context
from app.models.auth_schemas import AuthContext
from app.models.memory import MemoryRecord
from app.models.schemas import (
    ConflictResolveRequest,
    ConflictResolveResponse,
    MemoryResponse,
    SuccessResponse,
)
from app.services.conflict_service import ConflictService

router = APIRouter(prefix="/conflicts", tags=["Conflict Resolution"])


@router.post(
    "/resolve",
    response_model=ConflictResolveResponse,
    summary="Resolve conflicting memories",
)
@track_metrics(operation="resolve_conflict")
async def resolve_conflict(
    request: ConflictResolveRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ConflictResolveResponse:
    """
    Resolve conflicts between a set of memory records using the specified strategy.

    **Strategies:**
    - `latest_wins` — keep the most recently created memory
    - `confidence_weighted` — keep the highest-confidence memory
    - `source_trust` — keep the memory from the most-used source
    - `merge_flag` — flag all for manual merge (no deletion)
    - `manual_review` — flag all and defer resolution to humans

    The requesting agent must have access to the organisation that owns the memories.
    """
    # Verify org access
    if not auth.can_access_org(request.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to organisation {request.org_id}",
        )

    service = ConflictService(db)

    try:
        result = await service.resolve_conflict(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    return result


@router.get(
    "/",
    response_model=List[MemoryResponse],
    summary="List conflicting memories for an organisation",
)
@track_metrics(operation="list_conflicts")
async def list_conflicts(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> List[MemoryResponse]:
    """
    Return all memories currently flagged as conflicting for the given organisation.
    """
    if not auth.can_access_org(org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to organisation {org_id}",
        )

    service = ConflictService(db)
    memories = await service.detect_conflicts(org_id)

    return [MemoryResponse.model_validate(m) for m in memories]


@router.post(
    "/flag",
    response_model=SuccessResponse,
    summary="Flag memories as conflicting",
)
@track_metrics(operation="flag_conflicts")
async def flag_conflicts(
    memory_ids: List[UUID],
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> SuccessResponse:
    """
    Mark the specified memories as conflicting, queuing them for later resolution.
    """
    if not auth.can_access_org(org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to organisation {org_id}",
        )

    service = ConflictService(db)
    count = await service.flag_as_conflict(memory_ids)

    return SuccessResponse(
        message=f"Flagged {count} memories as conflicting",
        data={"flagged_count": count, "memory_ids": [str(m) for m in memory_ids]},
    )
