"""
Pydantic schemas for authentication.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, field_validator


# ============= User Schemas =============

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=100, description="Username")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str = Field(..., min_length=8, description="User password")
    org_id: Optional[UUID] = Field(None, description="Organization ID")
    is_superuser: bool = Field(default=False, description="Superuser status")


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: UUID
    is_active: bool
    is_superuser: bool
    org_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]
    
    model_config = {"from_attributes": True}


# ============= Authentication Schemas =============

class LoginRequest(BaseModel):
    """Schema for login request."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str = Field(..., description="Refresh token")


class TokenPayload(BaseModel):
    """Schema for token payload (internal use)."""
    sub: UUID  # User ID
    jti: str  # JWT ID
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    type: str  # "access" or "refresh"


# ============= API Key Schemas =============

class ApiKeyBase(BaseModel):
    """Base API key schema."""
    name: str = Field(..., min_length=1, max_length=255, description="API key name")
    description: Optional[str] = Field(None, description="API key description")


class ApiKeyCreate(ApiKeyBase):
    """Schema for creating an API key."""
    org_id: UUID = Field(..., description="Organization ID")
    agent_id: Optional[UUID] = Field(None, description="Agent ID")
    team_id: Optional[UUID] = Field(None, description="Team ID")
    scopes: List[str] = Field(default=["agent"], description="Allowed scopes")
    expires_in_days: Optional[int] = Field(None, gt=0, le=365, description="Expiration in days")
    
    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Validate scopes are valid."""
        valid_scopes = {"agent", "team", "org", "global"}
        for scope in v:
            if scope not in valid_scopes:
                raise ValueError(f"Invalid scope: {scope}")
        return v


class ApiKeyResponse(ApiKeyBase):
    """Schema for API key response."""
    id: UUID
    org_id: UUID
    agent_id: Optional[UUID]
    team_id: Optional[UUID]
    scopes: str
    is_active: bool
    last_used_at: Optional[datetime]
    usage_count: int
    expires_at: Optional[datetime]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(ApiKeyResponse):
    """Schema for API key creation response (includes plain key)."""
    api_key: str = Field(..., description="Plain API key (only shown once)")


class ApiKeyListResponse(BaseModel):
    """Schema for listing API keys."""
    keys: List[ApiKeyResponse]
    total: int


# ============= Permission Schemas =============

class PermissionCreate(BaseModel):
    """Schema for creating a permission."""
    resource: str = Field(..., description="Resource name")
    action: str = Field(..., description="Action name")
    user_id: Optional[UUID] = None
    api_key_id: Optional[UUID] = None
    org_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    team_id: Optional[UUID] = None


class PermissionResponse(BaseModel):
    """Schema for permission response."""
    id: UUID
    resource: str
    action: str
    user_id: Optional[UUID]
    api_key_id: Optional[UUID]
    org_id: Optional[UUID]
    agent_id: Optional[UUID]
    team_id: Optional[UUID]
    created_at: datetime
    
    model_config = {"from_attributes": True}


# ============= Auth Context Schemas =============

class AuthContext(BaseModel):
    """Schema for authentication context (attached to requests)."""
    user_id: Optional[UUID] = None
    api_key_id: Optional[UUID] = None
    org_id: UUID
    agent_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    scopes: List[str] = Field(default_factory=list)
    is_superuser: bool = False
    
    def has_scope(self, scope: str) -> bool:
        """Check if context has a specific scope."""
        return scope in self.scopes or self.is_superuser
    
    def can_access_org(self, org_id: UUID) -> bool:
        """Check if can access an organization."""
        return self.org_id == org_id or self.is_superuser
    
    def can_access_agent(self, agent_id: UUID) -> bool:
        """Check if can access an agent."""
        if self.is_superuser:
            return True
        if self.agent_id == agent_id:
            return True
        if "org" in self.scopes or "team" in self.scopes:
            return True
        return False


class PermissionCheck(BaseModel):
    """Schema for checking permissions."""
    resource: str = Field(..., description="Resource to check")
    action: str = Field(..., description="Action to check")
    org_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
