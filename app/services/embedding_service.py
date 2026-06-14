"""
Embedding service — wraps sentence-transformers for generating vector embeddings.
The model is loaded once at startup and reused across requests.
"""
import asyncio
import logging
from typing import List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model = None
_model_lock = asyncio.Lock()


async def _get_model():
    """Lazy-load the sentence-transformer model (thread-safe)."""
    global _model
    if _model is None:
        async with _model_lock:
            if _model is None:
                from app.configs.settings import settings
                try:
                    from sentence_transformers import SentenceTransformer
                    logger.info(f"Loading embedding model: {settings.embedding_model}")
                    # Load in executor to avoid blocking the event loop
                    loop = asyncio.get_event_loop()
                    _model = await loop.run_in_executor(
                        None,
                        lambda: SentenceTransformer(settings.embedding_model)
                    )
                    logger.info("Embedding model loaded successfully")
                except Exception as e:
                    logger.error(f"Failed to load embedding model: {e}")
                    _model = None
    return _model


class EmbeddingService:
    """Service for generating text embeddings."""

    def __init__(self):
        from app.configs.settings import settings
        self.model_name = settings.embedding_model
        self.max_length = settings.embedding_max_length
        self.vector_size = settings.qdrant_vector_size

    async def encode(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of floats (embedding vector), or None on failure
        """
        model = await _get_model()
        if model is None:
            return None

        try:
            # Truncate if too long
            truncated = text[:self.max_length * 4]  # rough char estimate

            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: model.encode(truncated, normalize_embeddings=True).tolist()
            )
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    async def encode_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors (None where failed)
        """
        model = await _get_model()
        if model is None:
            return [None] * len(texts)

        try:
            truncated = [t[:self.max_length * 4] for t in texts]
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: model.encode(truncated, normalize_embeddings=True).tolist()
            )
            return embeddings
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return [None] * len(texts)


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get (or create) the singleton EmbeddingService."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
