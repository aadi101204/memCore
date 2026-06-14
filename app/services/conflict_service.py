"""
Conflict resolution service — implements strategies for resolving conflicting memories.

Supported strategies:
  - LATEST_WINS       : Keep the most recently created memory.
  - CONFIDENCE_WEIGHTED: Keep the highest-confidence memory.
  - SOURCE_TRUST      : Keep the memory from the most-trusted source (by usage_count proxy).
  - MERGE_FLAG        : Mark all as conflicting, flag for manual review, return newest.
  - MANUAL_REVIEW     : Flag all memories with conflict_flag=True, return None (pending review).
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import MemoryRecord, ConflictStrategy
from app.models.schemas import ConflictResolveRequest, ConflictResolveResponse
from app.repositories import MemoryRepository

logger = logging.getLogger(__name__)


class ConflictService:
    """Service for conflict detection and resolution."""

    def __init__(self, db: AsyncSession):
        self.repo = MemoryRepository(db)

    async def resolve_conflict(
        self, request: ConflictResolveRequest
    ) -> ConflictResolveResponse:
        """
        Resolve a conflict between a set of memory records.

        Args:
            request: Conflict resolution request with memory IDs and strategy

        Returns:
            ConflictResolveResponse with the winning memory ID and details

        Raises:
            ValueError: If any memory ID is not found or doesn't belong to the org
        """
        # Fetch all memories
        memories = await self._fetch_and_validate(request.memory_ids, request.org_id)

        # Apply strategy
        winner, message = await self._apply_strategy(memories, request.strategy)

        # Mark losers as deleted (soft delete) and clear conflict flag on winner
        loser_ids = [m.id for m in memories if m.id != winner.id]
        await self._finalize_resolution(winner, loser_ids, request.strategy)

        return ConflictResolveResponse(
            resolved_memory_id=winner.id,
            strategy_used=request.strategy,
            merged_memories=request.memory_ids,
            message=message,
        )

    async def detect_conflicts(
        self, org_id: UUID, agent_id: Optional[UUID] = None
    ) -> List[MemoryRecord]:
        """Return all memories currently flagged as conflicting."""
        return await self.repo.get_conflicting_memories(org_id)

    async def flag_as_conflict(self, memory_ids: List[UUID]) -> int:
        """
        Flag a set of memories as conflicting (sets conflict_flag=True).

        Returns:
            Number of memories flagged
        """
        count = 0
        for mid in memory_ids:
            mem = await self.repo.get_by_id(mid)
            if mem:
                mem.conflict_flag = True
                await self.repo.update(mid, mem)
                count += 1
        return count

    # ========== Private Helpers ==========

    async def _fetch_and_validate(
        self, memory_ids: List[UUID], org_id: UUID
    ) -> List[MemoryRecord]:
        """Fetch and validate all memories belong to the given org."""
        memories = []
        for mid in memory_ids:
            mem = await self.repo.get_by_id(mid)
            if not mem:
                raise ValueError(f"Memory {mid} not found")
            if mem.org_id != org_id:
                raise ValueError(
                    f"Memory {mid} does not belong to org {org_id}"
                )
            memories.append(mem)

        if len(memories) < 2:
            raise ValueError("At least 2 memories required for conflict resolution")

        return memories

    async def _apply_strategy(
        self, memories: List[MemoryRecord], strategy: ConflictStrategy
    ) -> Tuple[MemoryRecord, str]:
        """Apply the given resolution strategy and return (winner, message)."""

        if strategy == ConflictStrategy.LATEST_WINS:
            winner = max(
                memories,
                key=lambda m: m.created_at or datetime.min,
            )
            return winner, f"Resolved via LATEST_WINS: kept memory created at {winner.created_at}"

        elif strategy == ConflictStrategy.CONFIDENCE_WEIGHTED:
            winner = max(memories, key=lambda m: float(m.confidence))
            return (
                winner,
                f"Resolved via CONFIDENCE_WEIGHTED: kept memory with confidence {winner.confidence:.3f}",
            )

        elif strategy == ConflictStrategy.SOURCE_TRUST:
            # Proxy for source trust: usage_count (more used = more trusted)
            winner = max(memories, key=lambda m: m.usage_count)
            return (
                winner,
                f"Resolved via SOURCE_TRUST: kept memory from most-used source (usage={winner.usage_count})",
            )

        elif strategy == ConflictStrategy.MERGE_FLAG:
            # Keep newest, flag all as conflicting, let downstream handle merge
            winner = max(
                memories,
                key=lambda m: m.created_at or datetime.min,
            )
            # Flag all (including winner) to indicate review needed
            for mem in memories:
                mem.conflict_flag = True
                await self.repo.update(mem.id, mem)
            return (
                winner,
                "Resolved via MERGE_FLAG: all memories flagged for manual merge review",
            )

        elif strategy == ConflictStrategy.MANUAL_REVIEW:
            # Flag all, return newest as placeholder winner (no soft-delete)
            for mem in memories:
                mem.conflict_flag = True
                await self.repo.update(mem.id, mem)
            winner = max(
                memories,
                key=lambda m: m.created_at or datetime.min,
            )
            return (
                winner,
                "Resolved via MANUAL_REVIEW: all memories flagged — awaiting human review",
            )

        else:
            raise ValueError(f"Unknown conflict strategy: {strategy}")

    async def _finalize_resolution(
        self,
        winner: MemoryRecord,
        loser_ids: List[UUID],
        strategy: ConflictStrategy,
    ) -> None:
        """Soft-delete losers and clear conflict flag on winner (unless MANUAL_REVIEW)."""
        if strategy == ConflictStrategy.MANUAL_REVIEW:
            # Don't delete anything — just flag
            return

        if strategy != ConflictStrategy.MERGE_FLAG:
            # Clear conflict flag on winner
            winner.conflict_flag = False
            await self.repo.update(winner.id, winner)

        # Soft-delete all losers (except MERGE_FLAG and MANUAL_REVIEW which keep them)
        if strategy not in (ConflictStrategy.MERGE_FLAG, ConflictStrategy.MANUAL_REVIEW):
            for lid in loser_ids:
                await self.repo.delete(lid)
                logger.info(f"Soft-deleted conflicting memory {lid} (loser in conflict resolution)")
