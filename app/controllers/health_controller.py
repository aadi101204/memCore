from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.configs.database import get_db
from app.configs.redis import get_redis
from app.configs.vector_db import get_vector_db
from app.configs.settings import settings
from app.models.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    vector_db = Depends(get_vector_db)
) -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
        Health status of all services
    """
    services = {}
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception:
        services["database"] = "unhealthy"
    
    # Check Redis
    try:
        await redis_client.ping()
        services["redis"] = "healthy"
    except Exception:
        services["redis"] = "unhealthy"
    
    # Check vector DB
    try:
        vector_db.get_client().get_collections()
        services["vector_db"] = "healthy"
    except Exception:
        services["vector_db"] = "unhealthy"
    
    # Overall status
    overall_status = "healthy" if all(
        s == "healthy" for s in services.values()
    ) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        services=services
    )
