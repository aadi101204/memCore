"""
Database models for memory records.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.configs.database import Base
import enum


class MemoryScope(str, enum.Enum):
    """Memory scope enumeration."""
    AGENT = "agent"
    TEAM = "team"
    ORG = "org"
    GLOBAL = "global"


class MemoryType(str, enum.Enum):
    """Memory type enumeration."""
    FACT = "fact"
    PREFERENCE = "preference"
    EXPERIENCE = "experience"
    PLAN = "plan"
    BUG = "bug"
    INSIGHT = "insight"
    OTHER = "other"


class ConflictStrategy(str, enum.Enum):
    """Conflict resolution strategy enumeration."""
    LATEST_WINS = "latest_wins"
    CONFIDENCE_WEIGHTED = "confidence_weighted"
    SOURCE_TRUST = "source_trust"
    MERGE_FLAG = "merge_flag"
    MANUAL_REVIEW = "manual_review"


class MemoryRecord(Base):
    """Memory record model."""
    
    __tablename__ = "memory_records"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Organizational Context
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    team_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Scope
    scope = Column(SQLEnum(MemoryScope), nullable=False, default=MemoryScope.AGENT, index=True)
    
    # Content
    content = Column(Text, nullable=False)
    memory_type = Column(SQLEnum(MemoryType), nullable=False, default=MemoryType.OTHER, index=True)
    
    # Metadata
    confidence = Column(Float, nullable=False, default=1.0)
    source_agent = Column(UUID(as_uuid=True), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Versioning
    version = Column(Integer, nullable=False, default=1)
    parent_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Conflict Management
    conflict_flag = Column(Boolean, nullable=False, default=False, index=True)
    
    # Vector Embedding Reference
    embedding_id = Column(String(255), nullable=True, index=True)
    
    # Usage Tracking
    usage_count = Column(Integer, nullable=False, default=0)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Soft Delete
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<MemoryRecord(id={self.id}, type={self.memory_type}, scope={self.scope})>"


class MemoryLink(Base):
    """Memory link model for creating relationships between memories."""
    
    __tablename__ = "memory_links"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Relationship
    from_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    to_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    relation_type = Column(String(50), nullable=False, index=True)
    
    # Weight
    weight = Column(Float, nullable=False, default=1.0)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    
    def __repr__(self) -> str:
        return f"<MemoryLink(from={self.from_id}, to={self.to_id}, type={self.relation_type})>"
