"""
API Key authentication handler for MDS Provider API.
Provides simple API key-based authentication as an alternative to Auth0.
"""

import secrets
from typing import Dict
from fastapi import HTTPException, status


class APIKeyHandler:
    """Handle API key authentication for third-party access."""

    def __init__(self):
        # In production, this would be stored in a secure database
        # For now, we'll use environment variables for demo purposes
        self.api_keys: Dict[str, Dict] = self._load_api_keys()
        self.key_prefix = "mds_"

    def _load_api_keys(self) -> Dict[str, Dict]:
        """Load API keys from environment variables and include defaults for local dev."""
        api_keys = {
            # Default test keys for local development and validation
            "mds_test_key_12345": {
                "provider_id": "test-provider-1",
                "permissions": ["read"],
                "active": True
            },
            "mds_demo_key_67890": {
                "provider_id": "test-provider-2",
                "permissions": ["read"],
                "active": True
            },
            "mds_washington_ddot_2024": {
                "provider_id": "washingtonddot",
                "permissions": ["read"],
                "active": True
            }
        }
        
        # Load from environment variables (format: API_KEY_PROVIDER=key:provider:permissions)
        import os
        for env_var, value in os.environ.items():
            if env_var.startswith("API_KEY_") and ":" in value:
                try:
                    key, provider, permissions_str = value.split(":", 2)
                    permissions = permissions_str.split(",")
                    api_keys[key] = {
                        "provider_id": provider,
                        "permissions": permissions,
                        "active": True
                    }
                except ValueError:
                    if ":" in value:
                        key, provider = value.split(":", 1)
                        api_keys[key] = {
                            "provider_id": provider,
                            "permissions": ["read"],
                            "active": True
                        }
        
        return api_keys

    def generate_api_key(self, provider_id: str) -> str:
        """
        Generate a new API key for a provider.
        
        Args:
            provider_id: Provider identifier
            
        Returns:
            Generated API key string
        """
        # Generate a secure random key
        random_part = secrets.token_urlsafe(32)
        api_key = f"{self.key_prefix}{random_part}"
        
        # Store the key (in production, store in database)
        self.api_keys[api_key] = {
            "provider_id": provider_id,
            "permissions": ["read"],
            "active": True
        }
        
        return api_key

    def validate_api_key(self, api_key: str) -> Dict[str, str]:
        """
        Validate API key and return provider information.
        
        Args:
            api_key: API key to validate
            
        Returns:
            Dict containing provider information
            
        Raises:
            HTTPException: If API key is invalid
        """
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key missing"
            )

        # Check if key exists and is active
        if api_key not in self.api_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )

        key_info = self.api_keys[api_key]
        if not key_info.get("active", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key is inactive"
            )

        return {
            "provider_id": key_info["provider_id"],
            "permissions": key_info.get("permissions", ["read"])
        }

    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            api_key: API key to revoke
            
        Returns:
            True if key was revoked, False if not found
        """
        if api_key in self.api_keys:
            self.api_keys[api_key]["active"] = False
            return True
        return False

    def list_api_keys(self) -> Dict[str, Dict]:
        """
        List all API keys (for admin purposes).
        
        Returns:
            Dict of API keys and their information
        """
        return self.api_keys.copy()


# Global API key handler instance
api_key_handler = APIKeyHandler()
