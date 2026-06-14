"""Vector database configuration (Qdrant) — async-safe implementation."""
import asyncio
from typing import Optional, List

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.configs.settings import settings


class VectorDB:
    """Vector database manager for Qdrant — uses AsyncQdrantClient for non-blocking I/O."""

    def __init__(self):
        """Initialize Qdrant clients (lazy — connect on first use)."""
        self.collection_name = settings.qdrant_collection_name
        self.vector_size = settings.qdrant_vector_size
        self._async_client: Optional[AsyncQdrantClient] = None
        self._sync_client: Optional[QdrantClient] = None

    @property
    def async_client(self) -> AsyncQdrantClient:
        if self._async_client is None:
            self._async_client = AsyncQdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            )
        return self._async_client

    @property
    def sync_client(self) -> QdrantClient:
        """Sync client for non-async contexts (e.g. health-check utility)."""
        if self._sync_client is None:
            self._sync_client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            )
        return self._sync_client

    async def initialize(self):
        """Create collection if it doesn't exist."""
        try:
            collections = await self.async_client.get_collections()
            existing = [col.name for col in collections.collections]

            if self.collection_name not in existing:
                await self.async_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                print(f"Created Qdrant collection: {self.collection_name}")
            else:
                print(f"Qdrant collection already exists: {self.collection_name}")
        except Exception as e:
            print(f"Warning: Could not connect to Qdrant: {e}. Vector search will be unavailable.")

    async def upsert_vector(
        self,
        point_id: str,
        vector: List[float],
        payload: Optional[dict] = None,
    ) -> bool:
        """Insert or update a vector point."""
        try:
            await self.async_client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload or {},
                    )
                ],
            )
            return True
        except Exception as e:
            print(f"Error upserting vector: {e}")
            return False

    async def search_vectors(
        self,
        query_vector: List[float],
        top_k: int = 10,
        score_threshold: float = 0.0,
        filter_conditions: Optional[dict] = None,
    ) -> List[dict]:
        """Search for similar vectors, returning list of {id, score, payload}."""
        try:
            from qdrant_client.models import Filter as QFilter, FieldCondition, MatchValue

            query_filter = None
            if filter_conditions:
                conditions = [
                    FieldCondition(key=key, match=MatchValue(value=str(value)))
                    for key, value in filter_conditions.items()
                ]
                if conditions:
                    query_filter = QFilter(must=conditions)

            results = await self.async_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=True,
            )
            return [
                {"id": str(r.id), "score": r.score, "payload": r.payload}
                for r in results
            ]
        except Exception as e:
            print(f"Error searching vectors: {e}")
            return []

    async def delete_vector(self, point_id: str) -> bool:
        """Delete a vector by ID."""
        try:
            await self.async_client.delete(
                collection_name=self.collection_name,
                points_selector=[point_id],
            )
            return True
        except Exception as e:
            print(f"Error deleting vector: {e}")
            return False

    def get_client(self) -> QdrantClient:
        """Get sync client (for health checks / legacy code)."""
        return self.sync_client


# Global vector DB instance
vector_db = VectorDB()


def get_vector_db() -> VectorDB:
    """Dependency for getting vector database."""
    return vector_db
