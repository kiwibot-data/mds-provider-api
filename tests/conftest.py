"""
Pytest configuration and fixtures for MDS Provider API tests.
"""

import asyncio
import pytest
from fastapi.testclient import TestClient
from typing import Generator
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
import jwt

from app.main import app
from app.config import settings, MDSConstants


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


@pytest.fixture(scope="function")
def mock_bigquery_service():
    """Fixture to mock the BigQuery service."""
    with patch("app.services.bigquery.bigquery_service", new_callable=AsyncMock) as mock_service:
        
        # Configure mock for vehicles endpoint
        mock_service.get_active_robot_list.return_value = [
            {"robot_id": "4F403"},
            {"robot_id": "4E006"}
        ]
        mock_service.get_robot_current_status.return_value = [
            {"robot_id": "4F403", "latitude": 1.0, "longitude": 2.0, "timestamp": datetime.utcnow()},
            {"robot_id": "4E006", "latitude": 3.0, "longitude": 4.0, "timestamp": datetime.utcnow()}
        ]
        mock_service.get_robot_location_data.return_value = {
            "robot_id": "4F403", "latitude": 1.0, "longitude": 2.0, "timestamp": datetime.utcnow()
        }
        mock_service.get_robot_locations.return_value = [
            {"robot_id": "4F403", "latitude": 1.0, "longitude": 2.0, "timestamp": datetime.utcnow()},
            {"robot_id": "4E006", "latitude": 3.0, "longitude": 4.0, "timestamp": datetime.utcnow()}
        ]

        # Configure mock for trips endpoint
        mock_service.get_robot_trips.return_value = [
            {
                "robot_id": "4F403",
                "job_id": "test-job-001",
                "trip_start": datetime.utcnow() - timedelta(hours=1),
                "trip_end": datetime.utcnow(),
                "trip_duration_seconds": 3600,
                "trip_distance_meters": 1500,
                "start_latitude": 1.0, "start_longitude": 2.0,
                "end_latitude": 1.1, "end_longitude": 2.1
            }
        ]
        mock_service.check_data_availability.return_value = True

        # Yield a dictionary of mocks to access them in tests
        yield {
            "vehicles": mock_service,
            "trips": mock_service
        }


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
        "start_longitude": -122.4194,
        "end_latitude": 37.7850,
        "end_longitude": -122.4094
    }


@pytest.fixture
def sample_event_data():
    """Sample event data for testing."""
    return {
        "robot_id": "4F403",
        "event_id": "event_4F403_step1",
        "event_type": "trip_end",
        "event_time": datetime.utcnow(),
        "latitude": 37.7850,
        "longitude": -122.4094,
        "event_data": None,
        "created_at": datetime.utcnow(),
        "job_id": "test-job-123"
    }


@pytest.fixture
def mds_response_headers():
    """Standard MDS response headers."""
    return {
        "Content-Type": MDSConstants.CONTENT_TYPE_JSON
    }


@pytest.fixture(scope="function")
def mock_cross_endpoint_service():
    """Fixture providing consistent mock data across trips, events, and telemetry endpoints.

    All three endpoints share the same job_ids so trip_ids are consistent.
    """
    job_ids = ["job-aaa-111", "job-bbb-222"]
    base_time = datetime.utcnow() - timedelta(hours=2)

    trips_data = [
        {
            "robot_id": "4F403",
            "job_id": job_ids[0],
            "trip_id": f"trip_{job_ids[0]}",
            "trip_start": base_time,
            "trip_end": base_time + timedelta(minutes=30),
            "trip_duration_seconds": 1800,
            "start_latitude": 38.9197, "start_longitude": -77.0218,
            "end_latitude": 38.9250, "end_longitude": -77.0300,
            "status": "completed",
            "user_id": "user1",
            "created_at": base_time,
            "updated_at": base_time,
        },
        {
            "robot_id": "4E006",
            "job_id": job_ids[1],
            "trip_id": f"trip_{job_ids[1]}",
            "trip_start": base_time + timedelta(minutes=5),
            "trip_end": base_time + timedelta(minutes=40),
            "trip_duration_seconds": 2100,
            "start_latitude": 38.9100, "start_longitude": -77.0100,
            "end_latitude": 38.9200, "end_longitude": -77.0200,
            "status": "completed",
            "user_id": "user2",
            "created_at": base_time,
            "updated_at": base_time,
        },
    ]

    events_data = [
        # trip_start for job 0
        {
            "robot_id": "4F403",
            "event_id": "event_4F403_start_0",
            "event_type": "trip_start",
            "event_time": base_time,
            "latitude": 38.9197, "longitude": -77.0218,
            "event_data": None,
            "created_at": base_time,
            "job_id": job_ids[0],
        },
        # trip_end for job 0
        {
            "robot_id": "4F403",
            "event_id": "event_4F403_end_0",
            "event_type": "trip_end",
            "event_time": base_time + timedelta(minutes=30),
            "latitude": 38.9250, "longitude": -77.0300,
            "event_data": None,
            "created_at": base_time + timedelta(minutes=30),
            "job_id": job_ids[0],
        },
        # trip_start for job 1
        {
            "robot_id": "4E006",
            "event_id": "event_4E006_start_1",
            "event_type": "trip_start",
            "event_time": base_time + timedelta(minutes=5),
            "latitude": 38.9100, "longitude": -77.0100,
            "event_data": None,
            "created_at": base_time + timedelta(minutes=5),
            "job_id": job_ids[1],
        },
        # trip_end for job 1
        {
            "robot_id": "4E006",
            "event_id": "event_4E006_end_1",
            "event_type": "trip_end",
            "event_time": base_time + timedelta(minutes=40),
            "latitude": 38.9200, "longitude": -77.0200,
            "event_data": None,
            "created_at": base_time + timedelta(minutes=40),
            "job_id": job_ids[1],
        },
    ]

    telemetry_data = trips_data  # Telemetry endpoint queries trips_processed

    with patch("app.services.bigquery.bigquery_service", new_callable=AsyncMock) as mock_service:
        mock_service.get_robot_trips.return_value = trips_data
        mock_service.get_robot_events.return_value = events_data
        mock_service.get_robot_telemetry.return_value = telemetry_data
        mock_service.check_data_availability.return_value = True
        # Patch at all import sites so every endpoint uses the mock
        with patch("app.endpoints.events.bigquery_service", mock_service), \
             patch("app.endpoints.telemetry.bigquery_service", mock_service), \
             patch("app.endpoints.trips.bigquery_module.bigquery_service", mock_service):
            yield {
                "service": mock_service,
                "job_ids": job_ids,
                "trips_data": trips_data,
                "events_data": events_data,
            }