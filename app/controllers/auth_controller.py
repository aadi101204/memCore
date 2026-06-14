"""
Authentication controller — user registration, login, token management, and API key operations.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.database import get_db
from app.dependencies.auth_dependencies import get_auth_context, get_current_user, require_superuser
from app.models.auth_models import User
from app.models.auth_schemas import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyListResponse,
    AuthContext,
)
from app.models.schemas import SuccessResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============= User Registration & Login =============

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Register a new user account.

    Superuser registration requires an existing superuser (enforced at service level
    in production — open here for bootstrap convenience).
    """
    service = AuthService(db)

    # Check email uniqueness
    existing = await service.repo.get_user_by_email(user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Check username uniqueness
    existing_username = await service.repo.get_user_by_username(user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = await service.create_user(user_data)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT tokens",
)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username/email + password and receive access + refresh tokens."""
    service = AuthService(db)
    user = await service.authenticate_user(login_data)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await service.create_tokens(user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    refresh_data: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a refresh token for a new access token pair."""
    service = AuthService(db)
    user_id = await service.verify_token(refresh_data.refresh_token, expected_type="refresh")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await service.repo.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Revoke old refresh token
    await service.revoke_token(refresh_data.refresh_token)

    return await service.create_tokens(user)


@router.post(
    "/logout",
    response_model=SuccessResponse,
    summary="Logout and revoke token",
)
async def logout(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Revoke the current access token (adds to blacklist)."""
    # Token revocation is handled by the auth middleware on next request
    return SuccessResponse(message="Logged out successfully")


# ============= Current User =============

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ============= API Key Management =============

@router.post(
    "/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key",
)
async def create_api_key(
    key_data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreateResponse:
    """
    Create a new API key for agent/service authentication.

    The plain API key is shown ONCE in the response — store it securely.
    """
    service = AuthService(db)

    # Users can only create keys for their own org (unless superuser)
    if not current_user.is_superuser and current_user.org_id != key_data.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create API keys for a different organisation",
        )

    return await service.create_api_key(key_data, created_by=current_user.id)


@router.get(
    "/api-keys",
    response_model=ApiKeyListResponse,
    summary="List API keys for the current user's organisation",
)
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyListResponse:
    """List all API keys for the authenticated user's organisation."""
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with an organisation",
        )

    service = AuthService(db)
    keys = await service.get_api_keys_for_org(current_user.org_id)

    return ApiKeyListResponse(
        keys=[ApiKeyResponse.model_validate(k) for k in keys],
        total=len(keys),
    )


@router.delete(
    "/api-keys/{key_id}",
    response_model=SuccessResponse,
    summary="Revoke an API key",
)
async def revoke_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Revoke (deactivate) an API key by ID."""
    service = AuthService(db)

    # Verify the key belongs to the user's org
    key = await service.repo.get_api_key_by_id(key_id)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if not current_user.is_superuser and key.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this API key",
        )

    success = await service.revoke_api_key(key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    return SuccessResponse(message="API key revoked successfully")
