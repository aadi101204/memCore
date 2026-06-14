"""
Memory service — business logic for memory CRUD and hybrid vector search.
"""
import logging
import math
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.settings import settings
from app.configs.vector_db import get_vector_db
from app.models.memory import MemoryRecord
from app.models.schemas import (
    MemoryCreate,
    MemoryUpdate,
    MemorySearchRequest,
    MemorySearchResult,
    MemoryResponse,
)
from app.repositories import MemoryRepository
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for memory operations."""

    def __init__(self, db: AsyncSession):
        self.repo = MemoryRepository(db)
        self.vector_db = get_vector_db()
        self.embedding_service = get_embedding_service()

    async def create_memory(self, memory_data: MemoryCreate) -> MemoryRecord:
        """
        Create a new memory record and generate its embedding.
        The embedding is upserted into Qdrant and the embedding_id stored on the record.
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

        # Persist to Postgres first (get ID)
        created = await self.repo.create(memory_record)

        # Generate and store embedding asynchronously (non-fatal on failure)
        await self._store_embedding(created)

        return created

    async def _store_embedding(self, memory: MemoryRecord) -> None:
        """Generate embedding for memory content and store in Qdrant."""
        try:
            vector = await self.embedding_service.encode(memory.content)
            if vector is None:
                return

            embedding_id = str(memory.id)
            payload = {
                "memory_id": str(memory.id),
                "org_id": str(memory.org_id),
                "agent_id": str(memory.agent_id),
                "team_id": str(memory.team_id) if memory.team_id else None,
                "scope": memory.scope.value if hasattr(memory.scope, 'value') else str(memory.scope),
                "memory_type": memory.memory_type.value if hasattr(memory.memory_type, 'value') else str(memory.memory_type),
                "created_at": memory.created_at.isoformat() if memory.created_at else None,
                "is_deleted": memory.is_deleted,
            }

            success = await self.vector_db.upsert_vector(
                point_id=embedding_id,
                vector=vector,
                payload=payload,
            )

            if success:
                # Update embedding_id on the record
                await self.repo.update(memory.id, memory)
                memory.embedding_id = embedding_id
        except Exception as e:
            logger.warning(f"Failed to store embedding for memory {memory.id}: {e}")

    async def get_memory(self, memory_id: UUID) -> Optional[MemoryRecord]:
        """Get a memory by ID and increment usage."""
        memory = await self.repo.get_by_id(memory_id)
        if memory:
            await self.repo.increment_usage(memory_id)
        return memory

    async def update_memory(
        self, memory_id: UUID, memory_update: MemoryUpdate
    ) -> Optional[MemoryRecord]:
        """Update a memory record and refresh its embedding if content changed."""
        existing = await self.repo.get_by_id(memory_id)
        if not existing:
            return None

        content_changed = (
            memory_update.content is not None
            and memory_update.content != existing.content
        )

        # Apply field updates
        update_data = memory_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "ttl" and value is not None:
                existing.expires_at = datetime.utcnow() + timedelta(seconds=value)
            elif field != "ttl":
                setattr(existing, field, value)

        updated = await self.repo.update(memory_id, existing)

        # Re-embed if content changed
        if content_changed and updated:
            await self._store_embedding(updated)

        return updated

    async def delete_memory(self, memory_id: UUID) -> bool:
        """Soft delete a memory and remove its vector."""
        success = await self.repo.delete(memory_id)
        if success:
            # Remove from Qdrant (non-fatal)
            try:
                await self.vector_db.delete_vector(str(memory_id))
            except Exception as e:
                logger.warning(f"Failed to delete vector for memory {memory_id}: {e}")
        return success

    async def search_memories(
        self, search_request: MemorySearchRequest
    ) -> Tuple[List[MemorySearchResult], int]:
        """
        Hybrid search: semantic vector search + metadata filter + scoring.

        Scoring formula:
            score = w_sem * semantic + w_rec * recency + w_conf * confidence + w_use * usage
        """
        # Build Postgres filters
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

        # Try vector search first
        vector_scores: dict[str, float] = {}
        try:
            query_vector = await self.embedding_service.encode(search_request.query)
            if query_vector:
                vector_filter = {"org_id": str(search_request.org_id)}
                if search_request.agent_id:
                    vector_filter["agent_id"] = str(search_request.agent_id)

                vector_results = await self.vector_db.search_vectors(
                    query_vector=query_vector,
                    top_k=search_request.top_k * 2,  # over-fetch for re-ranking
                    score_threshold=0.0,
                    filter_conditions=vector_filter,
                )
                vector_scores = {r["id"]: r["score"] for r in vector_results}
        except Exception as e:
            logger.warning(f"Vector search failed, falling back to metadata-only: {e}")

        # Fetch candidates from Postgres
        memories = await self.repo.get_all(
            skip=0,
            limit=search_request.top_k * 3,
            filters=filters,
        )

        if not memories:
            return [], 0

        # Hybrid scoring
        now = datetime.utcnow()
        scored: List[Tuple[MemoryRecord, float, float, float]] = []

        for mem in memories:
            # Semantic score (from Qdrant, 0–1)
            semantic = vector_scores.get(str(mem.id), 0.0)

            # Recency score: exponential decay, half-life = 7 days
            age_days = (now - mem.created_at.replace(tzinfo=None)).days if mem.created_at else 0
            recency = math.exp(-0.693 * age_days / 7.0)  # ln(2)/7

            # Confidence score (already 0–1)
            confidence = float(mem.confidence)

            # Usage score: log-normalised (cap at 100 uses)
            usage = min(math.log1p(mem.usage_count) / math.log1p(100), 1.0)

            # Weighted sum
            final_score = (
                settings.weight_semantic * semantic
                + settings.weight_recency * recency
                + settings.weight_confidence * confidence
                + settings.weight_usage * usage
            )

            scored.append((mem, final_score, semantic, recency))

        # Sort by score descending, limit to top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[: search_request.top_k]

        results = [
            MemorySearchResult(
                memory=MemoryResponse.model_validate(mem),
                score=round(score, 4),
                semantic_score=round(sem, 4),
                recency_score=round(rec, 4),
            )
            for mem, score, sem, rec in scored
        ]

        return results, len(results)
