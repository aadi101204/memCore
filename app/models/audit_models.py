"""
Audit log models for tracking data modifications.
"""
import uuid
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.configs.database import Base


class AuditLog(Base):
    """Audit log model for tracking all data modifications."""
    
    __tablename__ = "audit_logs"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Who
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    api_key_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # What
    action = Column(String(50), nullable=False, index=True)  # CREATE, UPDATE, DELETE, etc.
    resource_type = Column(String(100), nullable=False, index=True)  # memory, api_key, etc.
    resource_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Details
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    changes = Column(JSONB, nullable=True)  # Dict of changed fields
    
    # Context
    org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Request Metadata
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(255), nullable=True, index=True)
    
    # Tamper Protection
    hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_org_timestamp', 'org_id', 'timestamp'),
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(action={self.action}, resource={self.resource_type}/{self.resource_id})>"
    
    def compute_hash(self) -> str:
        """
        Compute tamper-proof hash of the audit log entry.
        
        Returns:
            SHA-256 hash of the entry
        """
        data = {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "api_key_id": str(self.api_key_id) if self.api_key_id else None,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": str(self.resource_id),
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
        
        # Create deterministic JSON string
        json_str = json.dumps(data, sort_keys=True, default=str)
        
        # Compute SHA-256 hash
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """
        Verify the integrity of the audit log entry.
        
        Returns:
            True if hash is valid, False otherwise
        """
        computed_hash = self.compute_hash()
        return computed_hash == self.hash
    
    @classmethod
    def create_log(
        cls,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        api_key_id: Optional[uuid.UUID] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        org_id: Optional[uuid.UUID] = None,
        agent_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> "AuditLog":
        """
        Factory method to create an audit log entry with computed hash.
        
        Args:
            action: Action performed (CREATE, UPDATE, DELETE, etc.)
            resource_type: Type of resource
            resource_id: ID of the resource
            user_id: ID of user who performed the action
            api_key_id: ID of API key used
            old_value: Previous value (for UPDATE/DELETE)
            new_value: New value (for CREATE/UPDATE)
            org_id: Organization context
            agent_id: Agent context
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request ID for tracing
        
        Returns:
            AuditLog: New audit log entry with computed hash
        """
        # Compute changes for UPDATE actions
        changes = None
        if action == "UPDATE" and old_value and new_value:
            changes = {}
            for key in set(old_value.keys()) | set(new_value.keys()):
                old_val = old_value.get(key)
                new_val = new_value.get(key)
                if old_val != new_val:
                    changes[key] = {
                        "old": old_val,
                        "new": new_val,
                    }
        
        # Create audit log entry
        log = cls(
            user_id=user_id,
            api_key_id=api_key_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            changes=changes,
            org_id=org_id,
            agent_id=agent_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        
        # Compute and set hash
        log.hash = log.compute_hash()
        
        return log
