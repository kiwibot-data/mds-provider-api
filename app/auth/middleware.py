"""
Authentication middleware for MDS Provider API.
"""

import sys
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

        # Development mode: Skip authentication if no auth headers provided
        # This helps with deployment testing when Auth0 is not configured
        from app.config import settings
        # In test environment, we want to explicitly test auth, so we disable this shortcut
        is_testing = "pytest" in sys.modules

        if settings.DEBUG and not is_testing and not request.headers.get("Authorization") and not request.headers.get("X-API-Key"):
            # Add default authentication for development
            request.state.auth = {
                "provider_id": settings.PROVIDER_ID,
                "auth_type": "development",
                "permissions": ["read"]
            }
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
            except HTTPException as e:
                # Return proper JSON error response for API key failures
                from fastapi.responses import JSONResponse
                from app.config import settings
                return JSONResponse(
                    status_code=e.status_code,
                    content={
                        "error": e.detail.get("error", "authentication_error") if isinstance(e.detail, dict) else "authentication_error",
                        "error_description": e.detail.get("error_description", str(e.detail)) if isinstance(e.detail, dict) else str(e.detail)
                    },
                    headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
                )

        # Try JWT authentication (Auth0) if Authorization header looks like JWT
        if authorization:
            try:
                # Check if authorization header has proper format
                if not authorization.strip():
                    raise ValueError("Empty authorization header")
                
                # Handle different authorization header formats
                auth_parts = authorization.split(" ", 1)
                
                if len(auth_parts) == 2:
                    # Standard format: "Bearer <token>"
                    scheme, token = auth_parts
                    if scheme.lower() != "bearer":
                        raise ValueError("Invalid authorization scheme. Expected 'Bearer'")
                    
                    # Check if the Bearer token is actually an API key
                    if len(token) < 100 and '.' not in token:
                        try:
                            auth_data = api_key_handler.validate_api_key(token)
                            request.state.auth = {
                                "provider_id": auth_data["provider_id"],
                                "auth_type": "api_key",
                                "permissions": auth_data["permissions"]
                            }
                            response = await call_next(request)
                            return response
                        except HTTPException:
                            # If API key fails, continue with JWT validation
                            pass
                elif len(auth_parts) == 1:
                    # Direct token format: "<token>"
                    token = auth_parts[0]
                    
                    # Check if this looks like an API key instead of JWT
                    # JWT tokens are much longer and contain dots, API keys are shorter
                    if len(token) < 100 and '.' not in token:
                        # This looks like an API key, try API key authentication instead
                        try:
                            auth_data = api_key_handler.validate_api_key(token)
                            request.state.auth = {
                                "provider_id": auth_data["provider_id"],
                                "auth_type": "api_key",
                                "permissions": auth_data["permissions"]
                            }
                            response = await call_next(request)
                            return response
                        except HTTPException:
                            # If API key also fails, continue with JWT attempt
                            pass
                else:
                    raise ValueError("Invalid authorization header format")
                
                # Validate token is not empty
                if not token.strip():
                    raise ValueError("Empty token in authorization header")
                
                auth_data = jwt_handler.validate_token_and_extract_claims(token)
                # Add authentication data to request state
                request.state.auth = {
                    "provider_id": auth_data["provider_id"],
                    "auth_type": "jwt",
                    "claims": auth_data["claims"]
                }
                response = await call_next(request)
                return response
            except HTTPException as e:
                # Return proper JSON error response for JWT failures
                from fastapi.responses import JSONResponse
                from app.config import settings
                return JSONResponse(
                    status_code=e.status_code,
                    content={
                        "error": e.detail.get("error", "authentication_error") if isinstance(e.detail, dict) else "authentication_error",
                        "error_description": e.detail.get("error_description", str(e.detail)) if isinstance(e.detail, dict) else str(e.detail)
                    },
                    headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
                )
            except ValueError as e:
                from fastapi.responses import JSONResponse
                from app.config import settings
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "invalid_authorization_header",
                        "error_description": f"Invalid authorization header: {str(e)}"
                    },
                    headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
                )
            except Exception as e:
                from fastapi.responses import JSONResponse
                from app.config import settings
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": "authentication_failed",
                        "error_description": f"Authentication failed: {str(e)}"
                    },
                    headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
                )

        # No valid authentication found
        from fastapi.responses import JSONResponse
        from app.config import settings
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "authentication_required",
                "error_description": "Authentication required. Provide either X-API-Key header or Authorization: Bearer <token>"
            },
            headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
        )


def get_current_provider_id(request: Request) -> str:
    """
    Extracts provider_id from request state.
    """
    if not hasattr(request.state, "auth") or not request.state.auth:
        # This case should ideally not be reached in production due to middleware
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return request.state.auth.get("provider_id")


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