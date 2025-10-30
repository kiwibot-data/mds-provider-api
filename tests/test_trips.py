"""
Tests for trips endpoints.
"""

from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta
import pytest
from fastapi import HTTPException, status


class TestTripsEndpoint:
    """Tests for /trips endpoint."""

    def test_get_trips_unauthorized(self, client):
        """Test trips endpoint without authentication."""
        with pytest.raises(HTTPException) as exc_info:
            client.get("/trips/")
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_trips_missing_end_time(self, client, auth_headers, mock_jwt_handler):
        """Test trips endpoint without required end_time parameter."""
        response = client.get("/trips", headers=auth_headers)
        assert response.status_code == 422  # Validation error

    def test_get_trips_invalid_end_time_format(self, client, auth_headers, mock_jwt_handler):
        """Test trips endpoint with invalid end_time format."""
        response = client.get("/trips?end_time=invalid-format", headers=auth_headers)
        assert response.status_code == 400

        data = response.json()
        assert "error" in data
        assert data["error"] == "invalid_end_time"

    def test_get_trips_future_time(self, client, auth_headers, mock_jwt_handler):
        """Test trips endpoint with future end_time."""
        future_time = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%dT%H")

        response = client.get(f"/trips?end_time={future_time}", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        assert "error" in data
        assert data["error"] == "future_time"

    def test_get_trips_before_operations(self, client, auth_headers, mock_jwt_handler):
        """Test trips endpoint with time before operations started."""
        old_time = "2021-01-01T12"

        response = client.get(f"/trips?end_time={old_time}", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        assert "error" in data
        assert data["error"] == "no_operation"

    def test_get_trips_success(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test successful trips retrieval."""
        # Use a valid past hour
        end_time = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%dT%H")

        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert "trips" in data
        assert isinstance(data["trips"], list)

        # Verify BigQuery service was called
        mock_bigquery_service["trips"].get_robot_trips.assert_called_once()

    def test_get_trips_empty_result(self, client, auth_headers, mock_jwt_handler):
        """Test trips endpoint with no trip data."""
        with patch("app.endpoints.trips.bigquery_module.bigquery_service") as mock_service:
            mock_service.get_robot_trips = AsyncMock(return_value=[])
            mock_service.check_data_availability = AsyncMock(return_value=True)

            end_time = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%dT%H")
            response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
            assert response.status_code == 200

            data = response.json()
            assert data["trips"] == []

    def test_get_trips_data_processing(self, client, auth_headers, mock_jwt_handler):
        """Test trips endpoint when data is still being processed."""
        with patch("app.endpoints.trips.bigquery_module.bigquery_service") as mock_service:
            mock_service.check_data_availability = AsyncMock(return_value=False)

            # Use a recent hour (within 2 hours)
            end_time = (datetime.utcnow() - timedelta(minutes=30)).strftime("%Y-%m-%dT%H")
            response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
            assert response.status_code == 202

            data = response.json()
            assert "error" in data
            assert data["error"] == "data_processing"

    def test_trips_response_structure(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test that trips response has correct structure."""
        end_time = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%dT%H")

        response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()

        # Check required fields
        assert "version" in data
        assert "trips" in data

        # If we have trip data, check its structure
        if data["trips"]:
            trip = data["trips"][0]
            required_fields = [
                "provider_id", "device_id", "trip_id", "duration",
                "distance", "start_location", "end_location", 
                "start_time", "end_time", "trip_type"
            ]
            for field in required_fields:
                assert field in trip

            # Check location structure (GeoJSON)
            start_location = trip["start_location"]
            assert start_location["type"] == "Feature"
            assert "geometry" in start_location
            assert start_location["geometry"]["type"] == "Point"
            assert "coordinates" in start_location["geometry"]

    def test_trips_time_validation(self, client, auth_headers, mock_jwt_handler):
        """Test various time format validations."""
        test_cases = [
            ("2023-13-01T12", 400),  # Invalid month
            ("2023-12-32T12", 400),  # Invalid day
            ("2023-12-01T25", 400),  # Invalid hour
            ("2023-12-01", 400),     # Missing hour
            ("not-a-date", 400),     # Completely invalid
        ]

        for end_time, expected_status in test_cases:
            response = client.get(f"/trips?end_time={end_time}", headers=auth_headers)
            assert response.status_code == expected_status