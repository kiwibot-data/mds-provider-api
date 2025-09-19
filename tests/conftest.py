"""
Pytest configuration and fixtures for MDS Provider API tests.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Dict, Any
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import jwt
from datetime import datetime, timedelta

from app.main import app
from app.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_jwt_token():
    """Create a mock JWT token for testing."""
    payload = {
        "provider_id": settings.PROVIDER_ID,
        "sub": settings.PROVIDER_ID,
        "aud": settings.AUTH0_AUDIENCE,
        "iss": f"https://{settings.AUTH0_DOMAIN}/",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow()
    }

    # Create a simple token for testing (not cryptographically secure)
    token = jwt.encode(payload, "test-secret", algorithm="HS256")
    return f"Bearer {token}"


@pytest.fixture
def auth_headers(mock_jwt_token):
    """Create authentication headers for testing."""
    return {"Authorization": mock_jwt_token}


@pytest.fixture
def mock_bigquery_service():
    """Mock BigQuery service for testing."""
    with patch("app.services.bigquery.bigquery_service") as mock_service:
        # Configure mock methods
        mock_service.get_active_robot_list = AsyncMock(return_value=["4F403", "4E006"])
        mock_service.get_robot_current_status = AsyncMock(return_value=[
            {
                "robot_id": "4F403",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "timestamp": datetime.utcnow(),
                "accuracy": 0.8
            }
        ])
        mock_service.get_robot_trips = AsyncMock(return_value=[
            {
                "robot_id": "4F403",
                "job_id": "test-job-123",
                "trip_start": datetime.utcnow() - timedelta(hours=1),
                "trip_end": datetime.utcnow(),
                "trip_duration_seconds": 3600,
                "start_latitude": 37.7749,
                "start_longitude": -122.4194
            }
        ])
        mock_service.check_data_availability = AsyncMock(return_value=True)

        yield mock_service


@pytest.fixture
def mock_jwt_handler():
    """Mock JWT handler for testing."""
    with patch("app.auth.middleware.jwt_handler") as mock_handler:
        mock_handler.validate_token_and_extract_claims.return_value = {
            "provider_id": settings.PROVIDER_ID,
            "claims": {
                "provider_id": settings.PROVIDER_ID,
                "sub": settings.PROVIDER_ID
            }
        }
        yield mock_handler


@pytest.fixture
def sample_robot_data():
    """Sample robot data for testing."""
    return {
        "robot_id": "4F403",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "timestamp": datetime.utcnow(),
        "accuracy": 0.8
    }


@pytest.fixture
def sample_trip_data():
    """Sample trip data for testing."""
    return {
        "robot_id": "4F403",
        "job_id": "test-job-123",
        "trip_start": datetime.utcnow() - timedelta(hours=1),
        "trip_end": datetime.utcnow(),
        "trip_duration_seconds": 3600,
        "start_latitude": 37.7749,
        "start_longitude": -122.4194
    }


@pytest.fixture
def mds_response_headers():
    """Standard MDS response headers."""
    return {
        "Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"
    }