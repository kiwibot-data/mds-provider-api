"""
JWT token handling for MDS Provider API authentication.
"""

import jwt
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from app.config import settings
import requests
import json
from functools import lru_cache


class JWTHandler:
    """Handle JWT token verification and claims extraction."""

    def __init__(self):
        self.algorithm = settings.JWT_ALGORITHM
        self.auth0_domain = settings.AUTH0_DOMAIN
        self.audience = settings.AUTH0_AUDIENCE

    @lru_cache(maxsize=1)
    def get_jwks(self) -> Dict[str, Any]:
        """Get JSON Web Key Set from Auth0."""
        if not self.auth0_domain:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Auth0 domain not configured"
            )

        try:
            response = requests.get(f"https://{self.auth0_domain}/.well-known/jwks.json")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch JWKS: {str(e)}"
            )

    def get_signing_key(self, token: str) -> str:
        """Get the signing key for token verification."""
        try:
            # Decode header without verification to get kid
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            if not kid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing kid in header"
                )

            # Get JWKS and find matching key
            jwks = self.get_jwks()
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key"
            )

        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify JWT token and return claims.

        Args:
            token: JWT token string

        Returns:
            Dict containing token claims

        Raises:
            HTTPException: If token is invalid or verification fails
        """
        try:
            # Get signing key
            signing_key = self.get_signing_key(token)

            # Verify and decode token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=f"https://{self.auth0_domain}/"
            )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token audience"
            )
        except jwt.InvalidIssuerError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Token verification failed: {str(e)}"
            )

    def extract_provider_id(self, claims: Dict[str, Any]) -> str:
        """
        Extract provider_id from JWT claims.

        Args:
            claims: JWT token claims

        Returns:
            Provider ID string

        Raises:
            HTTPException: If provider_id is missing or invalid
        """
        # Check various possible claim locations for provider_id
        provider_id = claims.get("provider_id") or claims.get("sub") or claims.get("client_id")

        if not provider_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing provider_id claim"
            )

        # Validate provider_id format (should match configured provider)
        if provider_id != settings.PROVIDER_ID:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid provider_id in token"
            )

        return provider_id

    def validate_token_and_extract_claims(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token and extract required claims.

        Args:
            token: JWT token string

        Returns:
            Dict containing validated claims including provider_id
        """
        # Verify token
        claims = self.verify_token(token)

        # Extract and validate provider_id
        provider_id = self.extract_provider_id(claims)

        return {
            "provider_id": provider_id,
            "claims": claims
        }


# Global JWT handler instance
jwt_handler = JWTHandler()