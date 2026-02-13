"""
Authentication database models.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    String,
    Text,
    Integer,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.configs.database import Base


class User(Base):
    """User model for admin access."""
    
    __tablename__ = "users"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User Information
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_superuser = Column(Boolean, nullable=False, default=False)
    
    # Organizational Context
    org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class ApiKey(Base):
    """API key model for agent authentication."""
    
    __tablename__ = "api_keys"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Key Information
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Organizational Context
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    team_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Scopes and Permissions
    scopes = Column(Text, nullable=False, default="agent")  # Comma-separated: agent,team,org
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Usage Tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, name={self.name}, org_id={self.org_id})>"


class Permission(Base):
    """Permission model for fine-grained access control."""
    
    __tablename__ = "permissions"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Permission Details
    resource = Column(String(100), nullable=False, index=True)  # e.g., "memory", "conflict"
    action = Column(String(50), nullable=False, index=True)  # e.g., "read", "write", "delete"
    
    # Subject (who has the permission)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    api_key_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Scope
    org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    team_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<Permission(resource={self.resource}, action={self.action})>"


class TokenBlacklist(Base):
    """Token blacklist for revoked JWT tokens."""
    
    __tablename__ = "token_blacklist"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Token Information
    token_jti = Column(String(255), unique=True, nullable=False, index=True)  # JWT ID
    token_type = Column(String(50), nullable=False)  # "access" or "refresh"
    
    # User Context
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Timestamps
    blacklisted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self) -> str:
        return f"<TokenBlacklist(jti={self.token_jti}, type={self.token_type})>"
