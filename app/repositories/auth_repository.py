"""
Authentication repository for database operations.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.interfaces.repository import IRepository
from app.models.auth_models import User, ApiKey, Permission, TokenBlacklist


class AuthRepository(IRepository):
    """Repository for authentication operations."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session
    
    # ============= User Operations =============
    
    async def create_user(self, user: User) -> User:
        """Create a new user."""
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_username_or_email(self, identifier: str) -> Optional[User]:
        """Get user by username or email."""
        result = await self.session.execute(
            select(User).where(
                or_(User.username == identifier, User.email == identifier)
            )
        )
        return result.scalar_one_or_none()
    
    async def update_user(self, user_id: UUID, user: User) -> Optional[User]:
        """Update user."""
        existing = await self.get_user_by_id(user_id)
        if not existing:
            return None
        
        for key, value in user.__dict__.items():
            if not key.startswith("_") and value is not None:
                setattr(existing, key, value)
        
        existing.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(existing)
        return existing
    
    async def update_last_login(self, user_id: UUID) -> bool:
        """Update user's last login timestamp."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.last_login_at = datetime.utcnow()
        await self.session.commit()
        return True
    
    # ============= API Key Operations =============
    
    async def create_api_key(self, api_key: ApiKey) -> ApiKey:
        """Create a new API key."""
        self.session.add(api_key)
        await self.session.commit()
        await self.session.refresh(api_key)
        return api_key
    
    async def get_api_key_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        """Get API key by hash."""
        result = await self.session.execute(
            select(ApiKey).where(
                and_(
                    ApiKey.key_hash == key_hash,
                    ApiKey.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_api_key_by_id(self, key_id: UUID) -> Optional[ApiKey]:
        """Get API key by ID."""
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        return result.scalar_one_or_none()
    
    async def get_api_keys_by_org(self, org_id: UUID) -> List[ApiKey]:
        """Get all API keys for an organization."""
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.org_id == org_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def update_api_key_usage(self, key_id: UUID) -> bool:
        """Update API key usage statistics."""
        api_key = await self.get_api_key_by_id(key_id)
        if not api_key:
            return False
        
        api_key.last_used_at = datetime.utcnow()
        api_key.usage_count += 1
        await self.session.commit()
        return True
    
    async def revoke_api_key(self, key_id: UUID) -> bool:
        """Revoke an API key."""
        api_key = await self.get_api_key_by_id(key_id)
        if not api_key:
            return False
        
        api_key.is_active = False
        await self.session.commit()
        return True
    
    async def delete_expired_api_keys(self) -> int:
        """Delete expired API keys."""
        now = datetime.utcnow()
        result = await self.session.execute(
            select(ApiKey).where(
                and_(
                    ApiKey.expires_at <= now,
                    ApiKey.is_active == True
                )
            )
        )
        expired_keys = list(result.scalars().all())
        
        for key in expired_keys:
            key.is_active = False
        
        await self.session.commit()
        return len(expired_keys)
    
    # ============= Permission Operations =============
    
    async def create_permission(self, permission: Permission) -> Permission:
        """Create a new permission."""
        self.session.add(permission)
        await self.session.commit()
        await self.session.refresh(permission)
        return permission
    
    async def get_permissions_for_user(self, user_id: UUID) -> List[Permission]:
        """Get all permissions for a user."""
        result = await self.session.execute(
            select(Permission).where(Permission.user_id == user_id)
        )
        return list(result.scalars().all())
    
    async def get_permissions_for_api_key(self, api_key_id: UUID) -> List[Permission]:
        """Get all permissions for an API key."""
        result = await self.session.execute(
            select(Permission).where(Permission.api_key_id == api_key_id)
        )
        return list(result.scalars().all())
    
    async def check_permission(
        self,
        resource: str,
        action: str,
        user_id: Optional[UUID] = None,
        api_key_id: Optional[UUID] = None
    ) -> bool:
        """Check if a permission exists."""
        query = select(Permission).where(
            and_(
                Permission.resource == resource,
                Permission.action == action
            )
        )
        
        if user_id:
            query = query.where(Permission.user_id == user_id)
        if api_key_id:
            query = query.where(Permission.api_key_id == api_key_id)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
    
    # ============= Token Blacklist Operations =============
    
    async def blacklist_token(self, token_blacklist: TokenBlacklist) -> TokenBlacklist:
        """Add a token to the blacklist."""
        self.session.add(token_blacklist)
        await self.session.commit()
        await self.session.refresh(token_blacklist)
        return token_blacklist
    
    async def is_token_blacklisted(self, jti: str) -> bool:
        """Check if a token is blacklisted."""
        result = await self.session.execute(
            select(TokenBlacklist).where(TokenBlacklist.token_jti == jti)
        )
        return result.scalar_one_or_none() is not None
    
    async def cleanup_expired_tokens(self) -> int:
        """Remove expired tokens from blacklist."""
        now = datetime.utcnow()
        result = await self.session.execute(
            select(TokenBlacklist).where(TokenBlacklist.expires_at <= now)
        )
        expired_tokens = list(result.scalars().all())
        
        for token in expired_tokens:
            await self.session.delete(token)
        
        await self.session.commit()
        return len(expired_tokens)
