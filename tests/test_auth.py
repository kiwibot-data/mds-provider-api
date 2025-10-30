"""
Tests for authentication middleware and JWT handling.
"""

import pytest
from fastapi import HTTPException, status
from unittest.mock import MagicMock, patch

from app.config import settings


class TestAuthMiddleware:
    """
    Tests for the authentication middleware.
    """

    def test_public_endpoints_are_accessible(self, client):
        """Test that public endpoints are accessible without authentication."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
        assert response.json()["status"] == "healthy"

    def test_protected_endpoints_require_auth(self, client):
        """Test that protected endpoints require authentication."""
        with pytest.raises(HTTPException) as exc_info:
            client.get("/vehicles/")
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_token_success(self, client, auth_headers, mock_jwt_handler):
        """Test successful authentication with a valid JWT."""
        response = client.get("/vehicles/", headers=auth_headers)
        assert response.status_code == 200
        mock_jwt_handler.validate_token_and_extract_claims.assert_called_once()

    def test_missing_authorization_header(self, client):
        """Test that a missing authorization header results in an error."""
        with pytest.raises(HTTPException) as exc_info:
            client.get("/vehicles/")
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_authorization_scheme(self, client):
        """Test that an invalid authorization scheme (e.g., 'Basic') is rejected."""
        headers = {"Authorization": "Basic some_token"}
        with pytest.raises(HTTPException) as exc_info:
            client.get("/vehicles/", headers=headers)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid authorization scheme" in exc_info.value.detail

    def test_malformed_authorization_header(self, client):
        """Test that a malformed authorization header is rejected."""
        headers = {"Authorization": "Bearer"}  # Missing token
        with pytest.raises(HTTPException) as exc_info:
            client.get("/vehicles/", headers=headers)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid authorization header format" in exc_info.value.detail

    def test_invalid_token_failure(self, client, mock_jwt_handler):
        """Test that an invalid JWT results in an authentication failure."""
        headers = {"Authorization": "Bearer invalid_token"}
        mock_jwt_handler.validate_token_and_extract_claims.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
        with pytest.raises(HTTPException) as exc_info:
            client.get("/vehicles/", headers=headers)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token" in exc_info.value.detail


class TestJWTHandler:
    """Tests for JWT token handling."""

    @patch("app.auth.jwt_handler.requests.get")
    def test_get_jwks_success(self, mock_get):
        """Test successful JWKS retrieval."""
        from app.auth.jwt_handler import JWTHandler

        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        handler = JWTHandler()
        jwks = handler.get_jwks()

        assert "keys" in jwks
        mock_get.assert_called_once()

    def test_extract_provider_id_valid(self):
        """Test extracting provider_id from valid claims."""
        from app.auth.jwt_handler import JWTHandler

        handler = JWTHandler()
        claims = {"provider_id": settings.PROVIDER_ID}

        provider_id = handler.extract_provider_id(claims)
        assert provider_id == settings.PROVIDER_ID

    def test_extract_provider_id_from_sub(self):
        """Test extracting provider_id from sub claim."""
        from app.auth.jwt_handler import JWTHandler

        handler = JWTHandler()
        claims = {"sub": settings.PROVIDER_ID}

        provider_id = handler.extract_provider_id(claims)
        assert provider_id == settings.PROVIDER_ID

    def test_extract_provider_id_missing(self):
        """Test extracting provider_id when missing."""
        from app.auth.jwt_handler import JWTHandler
        from fastapi import HTTPException

        handler = JWTHandler()
        claims = {}

        with pytest.raises(HTTPException) as exc_info:
            handler.extract_provider_id(claims)

        assert exc_info.value.status_code == 401

    def test_extract_provider_id_invalid(self):
        """Test extracting invalid provider_id."""
        from app.auth.jwt_handler import JWTHandler
        from fastapi import HTTPException

        handler = JWTHandler()
        claims = {"provider_id": "invalid-provider"}

        with pytest.raises(HTTPException) as exc_info:
            handler.extract_provider_id(claims)

        assert exc_info.value.status_code == 403


class TestAuthenticationIntegration:
    """
    Integration tests for the full authentication flow.
    """

    def test_full_auth_flow_success(self, client, auth_headers, mock_jwt_handler):
        """Test the full authentication flow with a valid token."""
        response = client.get("/vehicles/", headers=auth_headers)
        assert response.status_code == 200
        mock_jwt_handler.validate_token_and_extract_claims.assert_called_once()

    def test_full_auth_flow_failure(self, client):
        """Test the full authentication flow with no token."""
        with pytest.raises(HTTPException) as exc_info:
            client.get("/vehicles/")
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED