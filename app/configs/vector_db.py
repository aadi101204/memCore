"""Vector database configuration (Qdrant)."""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.configs.settings import settings


class VectorDB:
    """Vector database manager for Qdrant."""
    
    def __init__(self):
        """Initialize Qdrant client."""
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        self.collection_name = settings.qdrant_collection_name
        self.vector_size = settings.qdrant_vector_size
    
    async def initialize(self):
        """Initialize collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [col.name for col in collections]
        
        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
    
    def get_client(self) -> QdrantClient:
        """
        Get Qdrant client instance.
        
        Returns:
            QdrantClient: Qdrant client
        """
        return self.client


# Global vector DB instance
vector_db = VectorDB()


def get_vector_db() -> VectorDB:
    """
    Dependency for getting vector database.
    
    Returns:
        VectorDB: Vector database instance
    """
    return vector_db
