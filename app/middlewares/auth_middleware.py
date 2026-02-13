"""
Authentication middleware for request authentication.
"""
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.configs.database import AsyncSessionLocal
from app.models.auth_schemas import AuthContext
from app.services.auth_service import AuthService


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to authenticate requests and attach auth context."""
    
    def __init__(self, app: ASGIApp):
        """Initialize auth middleware."""
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and authenticate."""
        # Skip authentication for certain paths
        if self._should_skip_auth(request.url.path):
            return await call_next(request)
        
        # Initialize auth context as None
        request.state.auth_context = None
        
        # Try to authenticate
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            auth_context = await self._authenticate_request(request, auth_service)
            
            if auth_context:
                request.state.auth_context = auth_context
        
        # Process request
        response = await call_next(request)
        return response
    
    def _should_skip_auth(self, path: str) -> bool:
        """Check if authentication should be skipped for a path."""
        skip_paths = [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/metrics",
            "/auth/login",
        ]
        
        for skip_path in skip_paths:
            if path == skip_path or path.startswith(skip_path + "/"):
                return True
        
        return False
    
    async def _authenticate_request(
        self,
        request: Request,
        auth_service: AuthService
    ) -> Optional[AuthContext]:
        """Authenticate a request using token or API key."""
        # Try API key first (X-API-Key header)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            auth_context = await auth_service.validate_api_key(api_key)
            if auth_context:
                return auth_context
        
        # Try JWT token (Authorization header)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            user_id = await auth_service.verify_token(token, expected_type="access")
            
            if user_id:
                # Get user and build auth context
                user = await auth_service.repo.get_user_by_id(user_id)
                if user and user.is_active:
                    return await auth_service.build_auth_context_from_user(user)
        
        return None
