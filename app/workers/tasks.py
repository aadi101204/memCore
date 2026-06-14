"""
Celery background tasks for memCore MaaS.
"""
import asyncio
import logging
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.tasks.embed_and_store", bind=True, max_retries=3)
def embed_and_store(self, memory_id: str):
    """
    Generate and store embedding for a memory record.
    Triggered after memory creation when async embedding is enabled.
    """
    async def _embed(memory_id: str):
        from app.configs.database import AsyncSessionLocal
        from app.configs.vector_db import vector_db
        from app.repositories.memory_repository import MemoryRepository
        from app.services.embedding_service import get_embedding_service

        async with AsyncSessionLocal() as session:
            repo = MemoryRepository(session)
            embedding_service = get_embedding_service()

            memory = await repo.get_by_id(UUID(memory_id))
            if not memory:
                logger.warning(f"Memory {memory_id} not found for embedding")
                return

            vector = await embedding_service.encode(memory.content)
            if vector is None:
                logger.error(f"Failed to generate embedding for memory {memory_id}")
                return

            payload = {
                "memory_id": str(memory.id),
                "org_id": str(memory.org_id),
                "agent_id": str(memory.agent_id),
                "scope": str(memory.scope),
                "memory_type": str(memory.memory_type),
            }

            await vector_db.upsert_vector(
                point_id=str(memory.id),
                vector=vector,
                payload=payload,
            )

            memory.embedding_id = str(memory.id)
            await repo.update(memory.id, memory)
            logger.info(f"Embedding stored for memory {memory_id}")

    try:
        _run_async(_embed(memory_id))
    except Exception as exc:
        logger.error(f"Embedding task failed for {memory_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(name="app.workers.tasks.cleanup_expired_memories")
def cleanup_expired_memories():
    """Soft-delete all expired memory records."""
    async def _cleanup():
        from app.configs.database import AsyncSessionLocal
        from app.repositories.memory_repository import MemoryRepository

        async with AsyncSessionLocal() as session:
            repo = MemoryRepository(session)
            expired = await repo.get_expired_memories()
            count = 0
            for mem in expired:
                await repo.delete(mem.id)
                count += 1
            logger.info(f"Cleaned up {count} expired memories")
            return count

    return _run_async(_cleanup())


@celery_app.task(name="app.workers.tasks.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Remove expired tokens from the blacklist table."""
    async def _cleanup():
        from app.configs.database import AsyncSessionLocal
        from app.repositories.auth_repository import AuthRepository

        async with AsyncSessionLocal() as session:
            repo = AuthRepository(session)
            count = await repo.cleanup_expired_tokens()
            logger.info(f"Cleaned up {count} expired blacklisted tokens")
            return count

    return _run_async(_cleanup())
