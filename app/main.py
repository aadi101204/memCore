"""
Main FastAPI application — memCore Memory-as-a-Service.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.configs.settings import settings
from app.configs.vector_db import vector_db
from app.controllers import (
    memory_router,
    working_memory_router,
    health_router,
    auth_router,
    conflict_router,
)
from app.middlewares import RequestLoggingMiddleware, RateLimitMiddleware
from app.middlewares.auth_middleware import AuthMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    print("Starting memCore MaaS API...")

    # Initialize vector database (non-fatal — app works without Qdrant but search degrades)
    try:
        await vector_db.initialize()
        print("Vector database initialised")
    except Exception as e:
        print(f"Warning: Vector database init failed: {e}")

    yield

    # Shutdown
    print("Shutting down memCore MaaS API...")


# Create FastAPI application
app = FastAPI(
    title="memCore — Memory-as-a-Service",
    description=(
        "Production-grade memory platform for AI agents. "
        "Provides persistent, scoped, semantically-searchable memory with "
        "conflict resolution, working memory (Redis), and audit logging."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# ─── Middleware (order matters — outermost first) ────────────────────────────

# CORS — must be added before custom middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware — populates request.state.auth_context
app.add_middleware(AuthMiddleware)

# Rate limiting — in-memory per-IP (Redis-backed in production)
app.add_middleware(RateLimitMiddleware, max_requests=100, window=60)

# Request logging + Prometheus metrics
app.add_middleware(RequestLoggingMiddleware)

# ─── Routers ────────────────────────────────────────────────────────────────

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(memory_router)
app.include_router(working_memory_router)
app.include_router(conflict_router)

# Prometheus metrics endpoint
if settings.enable_metrics:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


# ─── Root ───────────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — service info."""
    return {
        "service": "memCore MaaS",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
        "endpoints": {
            "health": "/health/",
            "auth": "/auth/",
            "memory": "/memory/",
            "working_memory": "/working/",
            "conflicts": "/conflicts/",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.api_workers,
    )
