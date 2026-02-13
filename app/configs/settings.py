"""
Application Configuration Module
Loads and validates all environment variables and application settings.
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Environment
    environment: str = Field(default="development", description="Environment name")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Database
    database_url: str = Field(..., description="PostgreSQL database URL")
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=0, description="Database max overflow")
    
    # Redis
    redis_url: str = Field(..., description="Redis connection URL")
    redis_max_connections: int = Field(default=50, description="Redis max connections")
    
    # Vector DB (Qdrant)
    qdrant_host: str = Field(default="localhost", description="Qdrant host")
    qdrant_port: int = Field(default=6333, description="Qdrant port")
    qdrant_collection_name: str = Field(default="memory_embeddings", description="Qdrant collection")
    qdrant_vector_size: int = Field(default=384, description="Vector embedding size")
    
    # Celery
    celery_broker_url: str = Field(..., description="Celery broker URL")
    celery_result_backend: str = Field(..., description="Celery result backend URL")
    
    # Embedding Model
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Sentence transformer model")
    embedding_batch_size: int = Field(default=32, description="Embedding batch size")
    embedding_max_length: int = Field(default=512, description="Max token length for embeddings")
    
    # OpenAI (Optional)
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    
    # Memory Configuration
    default_memory_ttl: int = Field(default=2592000, description="Default TTL in seconds (30 days)")
    max_memory_content_length: int = Field(default=10000, description="Max memory content length")
    default_top_k: int = Field(default=10, description="Default number of results to return")
    max_top_k: int = Field(default=100, description="Maximum number of results allowed")
    
    # Hybrid Ranking Weights
    weight_semantic: float = Field(default=0.6, description="Semantic similarity weight")
    weight_recency: float = Field(default=0.2, description="Recency weight")
    weight_confidence: float = Field(default=0.1, description="Confidence weight")
    weight_usage: float = Field(default=0.1, description="Usage count weight")
    
    # Security
    secret_key: str = Field(..., description="Secret key for JWT")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration")
    
    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    
    # Metrics
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9090, description="Metrics endpoint port")
    
    @field_validator("weight_semantic", "weight_recency", "weight_confidence", "weight_usage")
    @classmethod
    def validate_weights(cls, v: float) -> float:
        """Validate that weights are between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Weight must be between 0 and 1")
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() in ["development", "dev"]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() in ["production", "prod"]


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Application settings
    """
    return Settings()


# Export settings instance
settings = get_settings()
