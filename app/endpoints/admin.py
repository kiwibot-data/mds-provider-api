"""
Admin endpoints for MDS Provider API.
Provides API key management for third-party access.
"""

import logging
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.auth.api_key_handler import api_key_handler
from app.auth.middleware import get_current_provider_id
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class APIKeyRequest(BaseModel):
    """Request model for creating API keys."""
    provider_id: str
    permissions: List[str] = ["read"]


class APIKeyResponse(BaseModel):
    """Response model for API key operations."""
    api_key: str
    provider_id: str
    permissions: List[str]
    active: bool


class APIKeyListResponse(BaseModel):
    """Response model for listing API keys."""
    api_keys: List[Dict[str, str]]


@router.post(
    "/api-keys",
    response_model=APIKeyResponse,
    summary="Create API key",
    description="Create a new API key for third-party access."
)
async def create_api_key(
    request: Request,
    key_request: APIKeyRequest
):
    """
    Create a new API key for third-party access.
    
    This endpoint allows creating API keys for third parties to access the MDS Provider API.
    The API key can be used in the X-API-Key header for authentication.
    """
    try:
        # Authenticate the admin request (this would be more sophisticated in production)
        provider_id = get_current_provider_id(request)
        
        # In production, check if the requesting provider has admin permissions
        # For now, we'll allow any authenticated provider to create keys
        
        # Generate API key
        api_key = api_key_handler.generate_api_key(key_request.provider_id)
        
        logger.info(f"Created API key for provider {key_request.provider_id} by {provider_id}")
        
        return APIKeyResponse(
            api_key=api_key,
            provider_id=key_request.provider_id,
            permissions=key_request.permissions,
            active=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "error_description": str(e)}
        )


@router.get(
    "/api-keys",
    response_model=APIKeyListResponse,
    summary="List API keys",
    description="List all API keys (admin only)."
)
async def list_api_keys(request: Request):
    """
    List all API keys.
    
    This endpoint returns all API keys for administrative purposes.
    """
    try:
        # Authenticate the admin request
        provider_id = get_current_provider_id(request)
        
        # Get all API keys
        api_keys = api_key_handler.list_api_keys()
        
        # Format response (mask actual keys for security)
        formatted_keys = []
        for key, info in api_keys.items():
            formatted_keys.append({
                "key_preview": f"{key[:8]}...{key[-4:]}",  # Show first 8 and last 4 chars
                "provider_id": info["provider_id"],
                "permissions": info["permissions"],
                "active": info["active"]
            })
        
        logger.info(f"Listed API keys for admin {provider_id}")
        
        return APIKeyListResponse(api_keys=formatted_keys)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "error_description": str(e)}
        )


@router.delete(
    "/api-keys/{key_preview}",
    summary="Revoke API key",
    description="Revoke an API key by its preview."
)
async def revoke_api_key(
    request: Request,
    key_preview: str
):
    """
    Revoke an API key.
    
    This endpoint revokes an API key, making it inactive.
    """
    try:
        # Authenticate the admin request
        provider_id = get_current_provider_id(request)
        
        # Find the full key by preview (this is a simplified approach)
        # In production, you'd have a more secure way to identify keys
        api_keys = api_key_handler.list_api_keys()
        full_key = None
        
        for key, info in api_keys.items():
            if f"{key[:8]}...{key[-4:]}" == key_preview:
                full_key = key
                break
        
        if not full_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "key_not_found", "error_description": "API key not found"}
            )
        
        # Revoke the key
        success = api_key_handler.revoke_api_key(full_key)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "key_not_found", "error_description": "API key not found"}
            )
        
        logger.info(f"Revoked API key {key_preview} by admin {provider_id}")
        
        return {"message": "API key revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "error_description": str(e)}
        )
