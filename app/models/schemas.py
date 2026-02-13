"""
Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.memory import MemoryScope, MemoryType, ConflictStrategy


# ============= Memory Schemas =============

class MemoryBase(BaseModel):
    """Base memory schema."""
    content: str = Field(..., min_length=1, max_length=10000, description="Memory content")
    memory_type: MemoryType = Field(default=MemoryType.OTHER, description="Type of memory")
    scope: MemoryScope = Field(default=MemoryScope.AGENT, description="Memory scope")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")


class MemoryCreate(MemoryBase):
    """Schema for creating a memory."""
    org_id: UUID = Field(..., description="Organization ID")
    agent_id: UUID = Field(..., description="Agent ID")
    team_id: Optional[UUID] = Field(None, description="Team ID (for team scope)")
    ttl: Optional[int] = Field(None, gt=0, description="Time to live in seconds")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class MemoryUpdate(BaseModel):
    """Schema for updating a memory."""
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    memory_type: Optional[MemoryType] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    ttl: Optional[int] = Field(None, gt=0)


class MemoryResponse(MemoryBase):
    """Schema for memory response."""
    id: UUID
    org_id: UUID
    agent_id: UUID
    team_id: Optional[UUID]
    source_agent: UUID
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    version: int
    parent_id: Optional[UUID]
    conflict_flag: bool
    embedding_id: Optional[str]
    usage_count: int
    last_accessed_at: Optional[datetime]
    is_deleted: bool
    
    model_config = {"from_attributes": True}


class MemorySearchRequest(BaseModel):
    """Schema for memory search request."""
    query: str = Field(..., min_length=1, description="Search query")
    scope: Optional[MemoryScope] = Field(None, description="Filter by scope")
    memory_type: Optional[MemoryType] = Field(None, description="Filter by type")
    org_id: UUID = Field(..., description="Organization ID")
    agent_id: Optional[UUID] = Field(None, description="Agent ID (for agent scope)")
    team_id: Optional[UUID] = Field(None, description="Team ID (for team scope)")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum confidence threshold")
    include_deleted: bool = Field(default=False, description="Include soft-deleted memories")


class MemorySearchResult(BaseModel):
    """Schema for a single search result."""
    memory: MemoryResponse
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    semantic_score: float = Field(..., description="Semantic similarity score")
    recency_score: float = Field(..., description="Recency score")


class MemorySearchResponse(BaseModel):
    """Schema for memory search response."""
    results: List[MemorySearchResult]
    total: int
    query: str


# ============= Working Memory Schemas =============

class WorkingMemoryUpdate(BaseModel):
    """Schema for updating working memory."""
    session_id: str = Field(..., description="Session identifier")
    data: Dict[str, Any] = Field(..., description="Session data")
    ttl: Optional[int] = Field(default=3600, gt=0, description="TTL in seconds (default 1 hour)")


class WorkingMemoryResponse(BaseModel):
    """Schema for working memory response."""
    session_id: str
    data: Dict[str, Any]
    ttl: Optional[int]


# ============= Conflict Resolution Schemas =============

class ConflictResolveRequest(BaseModel):
    """Schema for conflict resolution request."""
    memory_ids: List[UUID] = Field(..., min_length=2, description="Conflicting memory IDs")
    strategy: ConflictStrategy = Field(..., description="Resolution strategy")
    org_id: UUID = Field(..., description="Organization ID")
    agent_id: UUID = Field(..., description="Requesting agent ID")


class ConflictResolveResponse(BaseModel):
    """Schema for conflict resolution response."""
    resolved_memory_id: UUID
    strategy_used: ConflictStrategy
    merged_memories: List[UUID]
    message: str


# ============= General Response Schemas =============

class ErrorResponse(BaseModel):
    """Schema for error responses."""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SuccessResponse(BaseModel):
    """Schema for success responses."""
    message: str
    data: Optional[Any] = None


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]  # service_name -> status
