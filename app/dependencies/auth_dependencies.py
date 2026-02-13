"""
Authentication dependencies for FastAPI routes.
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.database import get_db
from app.models.auth_schemas import AuthContext
from app.models.auth_models import User
from app.services.auth_service import AuthService


def get_auth_context(request: Request) -> AuthContext:
    """
    Get authentication context from request.
    
    Raises:
        HTTPException: If not authenticated
    """
    auth_context = getattr(request.state, "auth_context", None)
    
    if not auth_context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return auth_context


def get_optional_auth_context(request: Request) -> Optional[AuthContext]:
    """Get authentication context from request (optional)."""
    return getattr(request.state, "auth_context", None)


async def get_current_user(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user.
    
    Raises:
        HTTPException: If not authenticated with user account
    """
    if not auth_context.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    auth_service = AuthService(db)
    user = await auth_service.repo.get_user_by_id(auth_context.user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    return user


def require_superuser(
    user: User = Depends(get_current_user)
) -> User:
    """
    Require superuser access.
    
    Raises:
        HTTPException: If user is not a superuser
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    
    return user


def require_org_access(org_id: UUID):
    """
    Dependency factory to require access to a specific organization.
    
    Usage:
        @app.get("/org/{org_id}/memories")
        def get_memories(
            org_id: UUID,
            auth: AuthContext = Depends(require_org_access(org_id))
        ):
            ...
    """
    def _check_org_access(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not auth_context.can_access_org(org_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to organization {org_id}",
            )
        return auth_context
    
    return _check_org_access


def require_agent_access(agent_id: UUID):
    """
    Dependency factory to require access to a specific agent.
    
    Usage:
        @app.get("/agent/{agent_id}/memories")
        def get_memories(
            agent_id: UUID,
            auth: AuthContext = Depends(require_agent_access(agent_id))
        ):
            ...
    """
    def _check_agent_access(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not auth_context.can_access_agent(agent_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to agent {agent_id}",
            )
        return auth_context
    
    return _check_agent_access


def require_scope(scope: str):
    """
    Dependency factory to require a specific auth scope.
    
    Usage:
        @app.delete("/memory/{id}")
        def delete_memory(
            auth: AuthContext = Depends(require_scope("org"))
        ):
            ...
    """
    def _check_scope(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not auth_context.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{scope}' required",
            )
        return auth_context
    
    return _check_scope


class AuthContextValidator:
    """Validator for auth context permissions."""
    
    def __init__(self, auth_context: AuthContext):
        self.auth_context = auth_context
    
    def validate_org_access(self, org_id: UUID) -> None:
        """Validate access to an organization."""
        if not self.auth_context.can_access_org(org_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to organization {org_id}",
            )
    
    def validate_agent_access(self, agent_id: UUID) -> None:
        """Validate access to an agent."""
        if not self.auth_context.can_access_agent(agent_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to agent {agent_id}",
            )
    
    def validate_scope(self, scope: str) -> None:
        """Validate auth scope."""
        if not self.auth_context.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{scope}' required",
            )
