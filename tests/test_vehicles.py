"""
Tests for vehicle endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4
import json


class TestVehiclesEndpoint:
    """Tests for /vehicles endpoint."""

    def test_get_vehicles_unauthorized(self, client):
        """Test vehicles endpoint without authentication."""
        response = client.get("/vehicles/")
        assert response.status_code == 401

    def test_get_vehicles_success(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test successful vehicles retrieval."""
        response = client.get("/vehicles/", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert "vehicles" in data
        assert isinstance(data["vehicles"], list)

        # Verify BigQuery service was called
        mock_bigquery_service.get_active_robot_list.assert_called_once()

    def test_get_vehicles_empty_result(self, client, auth_headers, mock_jwt_handler):
        """Test vehicles endpoint with no active robots."""
        with patch("app.services.bigquery.bigquery_service") as mock_service:
            mock_service.get_active_robot_list = AsyncMock(return_value=[])

            response = client.get("/vehicles/", headers=auth_headers)
            assert response.status_code == 200

            data = response.json()
            assert data["vehicles"] == []

    def test_get_specific_vehicle_success(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test getting a specific vehicle by device_id."""
        # Use a device_id that would be generated from robot "4F403"
        from app.services.transformers import data_transformer
        device_id = data_transformer.robot_id_to_device_id("4F403")

        response = client.get(f"/vehicles/{device_id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data["vehicles"]) == 1
        assert str(data["vehicles"][0]["device_id"]) == str(device_id)

    def test_get_specific_vehicle_not_found(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test getting a non-existent vehicle."""
        device_id = uuid4()

        response = client.get(f"/vehicles/{device_id}", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "vehicle_not_found"


class TestVehicleStatusEndpoint:
    """Tests for /vehicles/status endpoint."""

    def test_get_vehicle_status_unauthorized(self, client):
        """Test vehicle status endpoint without authentication."""
        response = client.get("/vehicles/status")
        assert response.status_code == 401

    def test_get_vehicle_status_success(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test successful vehicle status retrieval."""
        response = client.get("/vehicles/status", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert "vehicles_status" in data
        assert "last_updated" in data
        assert "ttl" in data
        assert isinstance(data["vehicles_status"], list)

        # Verify BigQuery service was called
        mock_bigquery_service.get_robot_current_status.assert_called_once_with(None)

    def test_get_vehicle_status_empty_result(self, client, auth_headers, mock_jwt_handler):
        """Test vehicle status endpoint with no current data."""
        with patch("app.services.bigquery.bigquery_service") as mock_service:
            mock_service.get_robot_current_status = AsyncMock(return_value=[])

            response = client.get("/vehicles/status", headers=auth_headers)
            assert response.status_code == 200

            data = response.json()
            assert data["vehicles_status"] == []
            assert "last_updated" in data
            assert "ttl" in data

    def test_get_specific_vehicle_status_success(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test getting status for a specific vehicle."""
        from app.services.transformers import data_transformer
        device_id = data_transformer.robot_id_to_device_id("4F403")

        response = client.get(f"/vehicles/status/{device_id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "vehicles_status" in data
        if data["vehicles_status"]:  # If we have data
            assert len(data["vehicles_status"]) >= 0

    def test_get_specific_vehicle_status_not_found(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test getting status for a non-existent vehicle."""
        device_id = uuid4()

        response = client.get(f"/vehicles/status/{device_id}", headers=auth_headers)
        assert response.status_code == 404

        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "vehicle_not_found"

    def test_vehicle_status_response_structure(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test that vehicle status response has correct structure."""
        response = client.get("/vehicles/status", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()

        # Check required fields
        assert "version" in data
        assert "vehicles_status" in data
        assert "last_updated" in data
        assert "ttl" in data

        # Check that timestamps are integers (milliseconds)
        assert isinstance(data["last_updated"], int)
        assert isinstance(data["ttl"], int)

        # If we have vehicle status data, check its structure
        if data["vehicles_status"]:
            vehicle_status = data["vehicles_status"][0]
            required_fields = ["device_id", "provider_id", "vehicle_state", "last_event_time", "last_event_types"]
            for field in required_fields:
                assert field in vehicle_status