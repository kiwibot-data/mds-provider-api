"""
Tests for authentication middleware and JWT handling.
"""

import pytest
from unittest.mock import patch, MagicMock
import jwt
from datetime import datetime, timedelta

from app.config import settings


class TestAuthMiddleware:
    """Tests for authentication middleware."""

    def test_public_endpoints_no_auth(self, client):
        """Test that public endpoints don't require authentication."""
        public_endpoints = ["/", "/health", "/docs", "/redoc", "/openapi.json"]

        for endpoint in public_endpoints:
            response = client.get(endpoint)
            # Should not return 401 (may return other codes like 200, 404, etc.)
            assert response.status_code != 401

    def test_protected_endpoints_require_auth(self, client):
        """Test that protected endpoints require authentication."""
        protected_endpoints = ["/vehicles/", "/vehicles/status", "/trips", "/events/recent"]

        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401

    def test_missing_authorization_header(self, client):
        """Test request without Authorization header."""
        response = client.get("/vehicles/")
        assert response.status_code == 401

        data = response.json()
        assert "error" in data

    def test_invalid_authorization_scheme(self, client):
        """Test request with invalid authorization scheme."""
        headers = {"Authorization": "Basic invalid"}
        response = client.get("/vehicles/", headers=headers)
        assert response.status_code == 401

    def test_malformed_authorization_header(self, client):
        """Test request with malformed authorization header."""
        headers = {"Authorization": "Bearer"}  # Missing token
        response = client.get("/vehicles/", headers=headers)
        assert response.status_code == 401

    def test_valid_token_success(self, client, auth_headers, mock_jwt_handler, mock_bigquery_service):
        """Test request with valid token."""
        response = client.get("/vehicles/", headers=auth_headers)
        # Should not return 401
        assert response.status_code != 401
        # Verify JWT handler was called
        mock_jwt_handler.validate_token_and_extract_claims.assert_called_once()

    def test_options_request_no_auth(self, client):
        """Test that OPTIONS requests don't require authentication."""
        response = client.options("/vehicles/")
        # Should not return 401 for CORS preflight
        assert response.status_code != 401


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
    """Integration tests for authentication flow."""

    def test_full_auth_flow_success(self, client, mock_bigquery_service):
        """Test complete authentication flow with valid token."""
        # Create a test token (simplified for testing)
        with patch("app.auth.jwt_handler.jwt_handler") as mock_handler:
            mock_handler.validate_token_and_extract_claims.return_value = {
                "provider_id": settings.PROVIDER_ID,
                "claims": {"provider_id": settings.PROVIDER_ID}
            }

            headers = {"Authorization": "Bearer test-token"}
            response = client.get("/vehicles/", headers=headers)

            # Should succeed
            assert response.status_code == 200
            mock_handler.validate_token_and_extract_claims.assert_called_once_with("test-token")

    def test_full_auth_flow_failure(self, client):
        """Test complete authentication flow with invalid token."""
        from fastapi import HTTPException

        with patch("app.auth.jwt_handler.jwt_handler") as mock_handler:
            mock_handler.validate_token_and_extract_claims.side_effect = HTTPException(
                status_code=401, detail="Invalid token"
            )

            headers = {"Authorization": "Bearer invalid-token"}
            response = client.get("/vehicles/", headers=headers)

            assert response.status_code == 401