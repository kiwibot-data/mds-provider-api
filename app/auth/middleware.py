"""
Authentication middleware for MDS Provider API.
"""

from typing import Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.auth.jwt_handler import jwt_handler
from app.auth.api_key_handler import api_key_handler


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to handle JWT authentication for MDS Provider API."""

    def __init__(self, app):
        super().__init__(app)
        # Define public endpoints that don't require authentication
        self.public_endpoints = {
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through authentication middleware.
        Supports both JWT (Auth0) and API key authentication.

        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain

        Returns:
            Response object
        """
        # Skip authentication for public endpoints
        if request.url.path in self.public_endpoints:
            return await call_next(request)

        # Skip authentication for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Extract authorization header
        authorization = request.headers.get("Authorization")
        api_key = request.headers.get("X-API-Key")

        # Try API key authentication first (simpler for third parties)
        if api_key:
            try:
                auth_data = api_key_handler.validate_api_key(api_key)
                # Add authentication data to request state
                request.state.auth = {
                    "provider_id": auth_data["provider_id"],
                    "auth_type": "api_key",
                    "permissions": auth_data["permissions"]
                }
                response = await call_next(request)
                return response
            except HTTPException:
                # If API key fails, continue to JWT authentication
                pass

        # Try JWT authentication (Auth0)
        if authorization:
            try:
                scheme, token = authorization.split(" ", 1)
                if scheme.lower() != "bearer":
                    raise ValueError("Invalid authorization scheme")
                
                auth_data = jwt_handler.validate_token_and_extract_claims(token)
                # Add authentication data to request state
                request.state.auth = {
                    "provider_id": auth_data["provider_id"],
                    "auth_type": "jwt",
                    "claims": auth_data["claims"]
                }
                response = await call_next(request)
                return response
            except HTTPException:
                # Re-raise HTTP exceptions from JWT handler
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Authentication failed: {str(e)}"
                )

        # No valid authentication found
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide either X-API-Key header or Authorization: Bearer <token>"
        )


def get_current_provider_id(request: Request) -> str:
    """
    Extract provider_id from authenticated request.

    Args:
        request: FastAPI request object with authentication state

    Returns:
        Provider ID string

    Raises:
        HTTPException: If not authenticated or provider_id missing
    """
    if not hasattr(request.state, "auth"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Request not authenticated"
        )

    return request.state.auth["provider_id"]


def get_auth_claims(request: Request) -> dict:
    """
    Extract all authentication claims from request.

    Args:
        request: FastAPI request object with authentication state

    Returns:
        Dict containing all JWT claims

    Raises:
        HTTPException: If not authenticated
    """
    if not hasattr(request.state, "auth"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Request not authenticated"
        )

    return request.state.auth["claims"]