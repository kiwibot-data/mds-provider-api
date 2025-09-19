"""
Tests for data transformation services.
"""

import pytest
from uuid import UUID
from datetime import datetime, timedelta

from app.services.transformers import DataTransformer
from app.models.common import VehicleState, VehicleType, PropulsionType
from app.config import settings


class TestDataTransformer:
    """Tests for DataTransformer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.transformer = DataTransformer()

    def test_robot_id_to_device_id(self):
        """Test robot ID to device ID conversion."""
        robot_id = "4F403"
        device_id = self.transformer.robot_id_to_device_id(robot_id)

        assert isinstance(device_id, UUID)
        # Same robot_id should always produce same device_id
        device_id2 = self.transformer.robot_id_to_device_id(robot_id)
        assert device_id == device_id2

    def test_robot_id_to_device_id_different_robots(self):
        """Test that different robot IDs produce different device IDs."""
        device_id1 = self.transformer.robot_id_to_device_id("4F403")
        device_id2 = self.transformer.robot_id_to_device_id("4E006")

        assert device_id1 != device_id2

    def test_determine_vehicle_state_recent_data(self):
        """Test vehicle state determination with recent data."""
        location_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "robot_id": "4F403"
        }

        state = self.transformer.determine_vehicle_state(location_data)
        assert state == VehicleState.AVAILABLE

    def test_determine_vehicle_state_old_data(self):
        """Test vehicle state determination with old data."""
        old_time = datetime.utcnow() - timedelta(hours=2)
        location_data = {
            "timestamp": old_time.isoformat(),
            "robot_id": "4F403"
        }

        state = self.transformer.determine_vehicle_state(location_data)
        assert state == VehicleState.NON_CONTACTABLE

    def test_determine_vehicle_state_no_timestamp(self):
        """Test vehicle state determination without timestamp."""
        location_data = {"robot_id": "4F403"}

        state = self.transformer.determine_vehicle_state(location_data)
        assert state == VehicleState.MISSING

    def test_transform_location_to_geojson(self):
        """Test location transformation to GeoJSON."""
        lat, lng = 37.7749, -122.4194

        geojson = self.transformer.transform_location_to_geojson(lat, lng)

        assert geojson.type == "Feature"
        assert geojson.geometry.type == "Point"
        assert geojson.geometry.coordinates == [lng, lat]  # GeoJSON is [lng, lat]

    def test_transform_robot_to_vehicle(self):
        """Test robot data transformation to Vehicle model."""
        robot_data = {"robot_id": "4F403"}

        vehicle = self.transformer.transform_robot_to_vehicle(robot_data)

        assert vehicle.provider_id == settings.PROVIDER_ID
        assert vehicle.vehicle_type == VehicleType.ROBOT
        assert PropulsionType.ELECTRIC in vehicle.propulsion_types
        assert vehicle.mfgr == "Kiwibot"

    def test_transform_robot_to_vehicle_missing_id(self):
        """Test robot transformation without robot_id."""
        robot_data = {}

        with pytest.raises(ValueError, match="Robot data missing robot_id"):
            self.transformer.transform_robot_to_vehicle(robot_data)

    def test_transform_location_to_vehicle_status(self):
        """Test location data transformation to VehicleStatus."""
        location_data = {
            "robot_id": "4F403",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "timestamp": datetime.utcnow()
        }

        status = self.transformer.transform_location_to_vehicle_status(location_data)

        assert status.provider_id == settings.PROVIDER_ID
        assert isinstance(status.device_id, UUID)
        assert isinstance(status.vehicle_state, VehicleState)
        assert status.current_location is not None
        assert status.current_location.geometry.coordinates == [-122.4194, 37.7749]

    def test_transform_location_to_vehicle_status_missing_id(self):
        """Test location transformation without robot_id."""
        location_data = {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "timestamp": datetime.utcnow()
        }

        with pytest.raises(ValueError, match="Location data missing robot_id"):
            self.transformer.transform_location_to_vehicle_status(location_data)

    def test_batch_transform_vehicles(self):
        """Test batch transformation of multiple robots."""
        robot_data_list = [
            {"robot_id": "4F403"},
            {"robot_id": "4E006"},
            {"robot_id": "4E072"}
        ]

        vehicles = self.transformer.batch_transform_vehicles(robot_data_list)

        assert len(vehicles) == 3
        robot_ids = [v.device_id for v in vehicles]
        assert len(set(robot_ids)) == 3  # All unique

    def test_batch_transform_vehicles_with_errors(self):
        """Test batch transformation with some invalid data."""
        robot_data_list = [
            {"robot_id": "4F403"},
            {},  # Missing robot_id - should be skipped
            {"robot_id": "4E006"}
        ]

        vehicles = self.transformer.batch_transform_vehicles(robot_data_list)

        # Should only have 2 vehicles (one skipped due to error)
        assert len(vehicles) == 2

    def test_batch_transform_vehicle_status(self):
        """Test batch transformation of location data."""
        location_data_list = [
            {
                "robot_id": "4F403",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "timestamp": datetime.utcnow()
            },
            {
                "robot_id": "4E006",
                "latitude": 37.7849,
                "longitude": -122.4094,
                "timestamp": datetime.utcnow()
            }
        ]

        statuses = self.transformer.batch_transform_vehicle_status(location_data_list)

        assert len(statuses) == 2
        device_ids = [s.device_id for s in statuses]
        assert len(set(device_ids)) == 2  # All unique

    def test_get_event_types_for_state(self):
        """Test event type mapping for vehicle states."""
        test_cases = [
            (VehicleState.AVAILABLE, ["service_start"]),
            (VehicleState.ON_TRIP, ["trip_start"]),
            (VehicleState.NON_CONTACTABLE, ["comms_lost"]),
        ]

        for state, expected_events in test_cases:
            events = self.transformer._get_event_types_for_state(state)
            assert events == expected_events

    def test_generate_trip_id(self):
        """Test trip ID generation."""
        trip_data = {"job_id": "test-job-123"}

        trip_id = self.transformer._generate_trip_id(trip_data)

        assert isinstance(trip_id, UUID)
        # Same job should produce same trip_id
        trip_id2 = self.transformer._generate_trip_id(trip_data)
        assert trip_id == trip_id2