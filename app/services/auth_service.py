"""
Authentication service for handling business logic.
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from uuid import UUID

import bcrypt
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.settings import settings
from app.models.auth_models import User, ApiKey, TokenBlacklist
from app.models.auth_schemas import (
    UserCreate,
    LoginRequest,
    TokenResponse,
    TokenPayload,
    ApiKeyCreate,
    ApiKeyCreateResponse,
    AuthContext,
)
from app.repositories.auth_repository import AuthRepository


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: AsyncSession):
        self.repo = AuthRepository(db)
    
    # ============= Password Operations =============
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    
    # ============= User Operations =============
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user with hashed password."""
        user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=self.hash_password(user_data.password),
            org_id=user_data.org_id,
            is_superuser=user_data.is_superuser,
        )
        return await self.repo.create_user(user)
    
    async def authenticate_user(self, login_data: LoginRequest) -> Optional[User]:
        """Authenticate a user with username/email and password."""
        user = await self.repo.get_user_by_username_or_email(login_data.username)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not self.verify_password(login_data.password, user.hashed_password):
            return None
        
        # Update last login
        await self.repo.update_last_login(user.id)
        
        return user
    
    # ============= JWT Token Operations =============
    
    def _generate_jti(self) -> str:
        """Generate a unique JWT ID."""
        return secrets.token_urlsafe(32)
    
    def create_access_token(self, user_id: UUID, expires_delta: Optional[timedelta] = None) -> Tuple[str, str, int]:
        """
        Create an access token.
        
        Returns:
            Tuple of (token, jti, expires_in_seconds)
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
        
        expire = datetime.utcnow() + expires_delta
        jti = self._generate_jti()
        
        payload = {
            "sub": str(user_id),
            "jti": jti,
            "exp": int(expire.timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "type": "access",
        }
        
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
        expires_in = int(expires_delta.total_seconds())
        
        return token, jti, expires_in
    
    def create_refresh_token(self, user_id: UUID) -> Tuple[str, str]:
        """
        Create a refresh token (valid for 7 days).
        
        Returns:
            Tuple of (token, jti)
        """
        expires_delta = timedelta(days=7)
        expire = datetime.utcnow() + expires_delta
        jti = self._generate_jti()
        
        payload = {
            "sub": str(user_id),
            "jti": jti,
            "exp": int(expire.timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "type": "refresh",
        }
        
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
        
        return token, jti
    
    async def create_tokens(self, user: User) -> TokenResponse:
        """Create both access and refresh tokens for a user."""
        access_token, _, expires_in = self.create_access_token(user.id)
        refresh_token, _ = self.create_refresh_token(user.id)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )
    
    def decode_token(self, token: str) -> Optional[TokenPayload]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm]
            )
            
            return TokenPayload(
                sub=UUID(payload["sub"]),
                jti=payload["jti"],
                exp=payload["exp"],
                iat=payload["iat"],
                type=payload["type"],
            )
        except (jwt.InvalidTokenError, KeyError, ValueError):
            return None
    
    async def verify_token(self, token: str, expected_type: str = "access") -> Optional[UUID]:
        """
        Verify a token and return user ID if valid.
        
        Args:
            token: JWT token
            expected_type: Expected token type ("access" or "refresh")
        
        Returns:
            User ID if valid, None otherwise
        """
        payload = self.decode_token(token)
        
        if not payload:
            return None
        
        # Check token type
        if payload.type != expected_type:
            return None
        
        # Check if expired
        if datetime.utcnow().timestamp() > payload.exp:
            return None
        
        # Check if blacklisted
        if await self.repo.is_token_blacklisted(payload.jti):
            return None
        
        return payload.sub
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke a token by adding it to the blacklist."""
        payload = self.decode_token(token)
        
        if not payload:
            return False
        
        token_blacklist = TokenBlacklist(
            token_jti=payload.jti,
            token_type=payload.type,
            user_id=payload.sub,
            expires_at=datetime.fromtimestamp(payload.exp),
        )
        
        await self.repo.blacklist_token(token_blacklist)
        return True
    
    # ============= API Key Operations =============
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a random API key."""
        return f"maas_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    async def create_api_key(self, key_data: ApiKeyCreate, created_by: UUID) -> ApiKeyCreateResponse:
        """Create a new API key."""
        # Generate the key
        plain_key = self. generate_api_key()
        key_hash = self.hash_api_key(plain_key)
        
        # Calculate expiration
        expires_at = None
        if key_data.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)
        
        # Create API key record
        api_key = ApiKey(
            key_hash=key_hash,
            name=key_data.name,
            description=key_data.description,
            org_id=key_data.org_id,
            agent_id=key_data.agent_id,
            team_id=key_data.team_id,
            scopes=",".join(key_data.scopes),
            expires_at=expires_at,
            created_by=created_by,
        )
        
        created_key = await self.repo.create_api_key(api_key)
        
        # Return response with plain key (only shown once)
        return ApiKeyCreateResponse(
            id=created_key.id,
            name=created_key.name,
            description=created_key.description,
            org_id=created_key.org_id,
            agent_id=created_key.agent_id,
            team_id=created_key.team_id,
            scopes=created_key.scopes,
            is_active=created_key.is_active,
            last_used_at=created_key.last_used_at,
            usage_count=created_key.usage_count,
            expires_at=created_key.expires_at,
            created_at=created_key.created_at,
            api_key=plain_key,
        )
    
    async def validate_api_key(self, api_key: str) -> Optional[AuthContext]:
        """
        Validate an API key and return auth context.
        
        Args:
            api_key: Plain API key
        
        Returns:
            AuthContext if valid, None otherwise
        """
        key_hash = self.hash_api_key(api_key)
        db_key = await self.repo.get_api_key_by_hash(key_hash)
        
        if not db_key:
            return None
        
        # Check if expired
        if db_key.expires_at and db_key.expires_at <= datetime.utcnow():
            return None
        
        # Update usage statistics
        await self.repo.update_api_key_usage(db_key.id)
        
        # Build auth context
        scopes = db_key.scopes.split(",") if db_key.scopes else []
        
        return AuthContext(
            api_key_id=db_key.id,
            org_id=db_key.org_id,
            agent_id=db_key.agent_id,
            team_id=db_key.team_id,
            scopes=scopes,
            is_superuser=False,
        )
    
    async def get_api_keys_for_org(self, org_id: UUID) -> List[ApiKey]:
        """Get all API keys for an organization."""
        return await self.repo.get_api_keys_by_org(org_id)
    
    async def revoke_api_key(self, key_id: UUID) -> bool:
        """Revoke an API key."""
        return await self.repo.revoke_api_key(key_id)
    
    # ============= Permission Checking =============
    
    async def build_auth_context_from_user(self, user: User) -> AuthContext:
        """Build auth context from a user."""
        # Determine scopes based on user's organization
        scopes = ["agent", "team", "org"] if user.org_id else []
        
        return AuthContext(
            user_id=user.id,
            org_id=user.org_id,
            scopes=scopes,
            is_superuser=user.is_superuser,
        )
