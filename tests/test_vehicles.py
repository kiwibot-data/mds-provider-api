"""
Tests for vehicle endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4
import json
from fastapi.exceptions import HTTPException
from starlette import status


class TestVehiclesEndpoint:
    """
    Tests for the /vehicles endpoint.
    """

    def test_get_vehicles_unauthorized(self, client):
        """Test vehicles endpoint without authentication."""
        with pytest.raises(HTTPException) as exc_info:
            client.get("/vehicles/")
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_vehicles_success(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test successful vehicles retrieval."""
        response = client.get("/vehicles/", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert "vehicles" in data
        assert isinstance(data["vehicles"], list)
    
        # Verify BigQuery service was called
        mock_bigquery_service["vehicles"].get_active_robot_list.assert_awaited_once()

    def test_get_vehicles_empty_result(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test vehicles endpoint with no active robots."""
        mock_bigquery_service["vehicles"].get_active_robot_list.return_value = []
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
        assert data["vehicles"][0]["device_id"] == str(device_id)
        mock_bigquery_service["vehicles"].get_active_robot_list.assert_awaited_once()

    def test_get_specific_vehicle_not_found(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test getting a non-existent vehicle."""
        device_id = uuid4()

        response = client.get(f"/vehicles/{device_id}", headers=auth_headers)
        assert response.status_code == 404
        mock_bigquery_service["vehicles"].get_active_robot_list.assert_awaited_once()


class TestVehicleStatusEndpoint:
    """Test suite for vehicle status endpoints."""

    def test_get_vehicle_status_unauthorized(self, client):
        """Test vehicle status endpoint without authentication."""
        with pytest.raises(HTTPException) as exc_info:
            client.get("/vehicles/status")
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_all_vehicle_statuses_success(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test successful vehicle status retrieval for all vehicles."""
        response = client.get("/vehicles/status", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert "vehicles" in data
        assert isinstance(data["vehicles"], list)
    
        mock_bigquery_service["vehicles"].get_robot_current_status.assert_awaited_once_with(robot_ids=None)

    def test_get_all_vehicle_statuses_empty_result(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test vehicle status endpoint with no location data."""
        mock_bigquery_service["vehicles"].get_robot_current_status.return_value = []
        response = client.get("/vehicles/status", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["vehicles"] == []

    def test_get_specific_vehicle_status_success(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test getting status for a specific vehicle."""
        from app.services.transformers import data_transformer
        device_id = data_transformer.robot_id_to_device_id("4F403")
    
        response = client.get(f"/vehicles/status/{device_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["vehicles"]) == 1
        assert data["vehicles"][0]["device_id"] == str(device_id)
        mock_bigquery_service["vehicles"].get_active_robot_list.assert_awaited_once()
        mock_bigquery_service["vehicles"].get_robot_current_status.assert_awaited_once_with(robot_ids=["4F403"])

    def test_get_specific_vehicle_status_not_found(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test getting status for a non-existent vehicle."""
        device_id = uuid4()
    
        response = client.get(f"/vehicles/status/{device_id}", headers=auth_headers)
        assert response.status_code == 404
        mock_bigquery_service["vehicles"].get_active_robot_list.assert_awaited_once()

    def test_vehicle_status_response_structure(self, client, auth_headers, mock_bigquery_service, mock_jwt_handler):
        """Test that vehicle status response has correct structure."""
        response = client.get("/vehicles/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "last_updated" in data
        assert "ttl" in data
        assert "vehicles" in data
        # For paginated response, links should be present
        assert "links" in data