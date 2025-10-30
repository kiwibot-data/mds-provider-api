"""Tests for data transformation services (updated schema)."""

import pytest
from uuid import UUID
from datetime import datetime, timedelta

from app.services.transformers import DataTransformer
from app.models.common import VehicleState
from app.config import settings


class TestDataTransformer:
    def setup_method(self):
        self.transformer = DataTransformer()

    def test_robot_id_to_device_id(self):
        robot_id = "4F403"
        device_id = self.transformer.robot_id_to_device_id(robot_id)
        assert isinstance(device_id, UUID)
        assert self.transformer.robot_id_to_device_id(robot_id) == device_id

    def test_robot_id_to_device_id_different_robots(self):
        assert self.transformer.robot_id_to_device_id("4F403") != self.transformer.robot_id_to_device_id("4E006")

    def test_determine_vehicle_state_recent_data(self):
        location_data = {"timestamp": datetime.utcnow().isoformat(), "robot_id": "4F403"}
        assert self.transformer.determine_vehicle_state(location_data) == VehicleState.AVAILABLE

    def test_determine_vehicle_state_old_data(self):
        old_time = datetime.utcnow() - timedelta(hours=2)
        location_data = {"timestamp": old_time.isoformat(), "robot_id": "4F403"}
        assert self.transformer.determine_vehicle_state(location_data) == VehicleState.NON_CONTACTABLE

    def test_determine_vehicle_state_no_timestamp(self):
        assert self.transformer.determine_vehicle_state({"robot_id": "4F403"}) == VehicleState.MISSING

    def test_transform_location_to_geojson(self):
        lat, lng = 37.7749, -122.4194
        geojson = self.transformer.transform_location_to_geojson(lat, lng)
        assert geojson.geometry.coordinates == [lng, lat]

    def test_transform_robot_to_vehicle(self):
        vehicle = self.transformer.transform_robot_to_vehicle({"robot_id": "4F403"})
        assert vehicle.provider_id == settings.PROVIDER_ID
        # Enum preserved; accessor property returns legacy string
        assert vehicle.vehicle_type == vehicle.vehicle_type
        assert vehicle.vehicle_type_str == "robot"
        assert vehicle.propulsion_types[0].value == "electric"
        assert vehicle.mfgr == "Kiwibot"
        assert vehicle.accessibility_attributes is not None
        assert vehicle.accessibility_attributes.audio_cue is True

    def test_transform_robot_to_vehicle_missing_id(self):
        with pytest.raises(ValueError):
            self.transformer.transform_robot_to_vehicle({})

    def test_transform_location_to_vehicle_status(self):
        status = self.transformer.transform_location_to_vehicle_status({
            "robot_id": "4F403",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "timestamp": datetime.utcnow()
        })
        assert status.provider_id == settings.PROVIDER_ID
        assert isinstance(status.device_id, UUID)
        assert isinstance(status.vehicle_state, VehicleState)
        assert status.current_location is not None

    def test_transform_location_to_vehicle_status_missing_id(self):
        with pytest.raises(ValueError):
            self.transformer.transform_location_to_vehicle_status({"latitude": 0, "longitude": 0, "timestamp": datetime.utcnow()})

    def test_batch_transform_vehicles(self):
        vehicles = self.transformer.batch_transform_vehicles([
            {"robot_id": "4F403"}, {"robot_id": "4E006"}, {"robot_id": "4E072"}
        ])
        assert len(vehicles) == 3
        assert len({v.device_id for v in vehicles}) == 3

    def test_batch_transform_vehicles_with_errors(self):
        vehicles = self.transformer.batch_transform_vehicles([
            {"robot_id": "4F403"}, {}, {"robot_id": "4E006"}
        ])
        assert len(vehicles) == 2

    def test_batch_transform_vehicle_status(self):
        statuses = self.transformer.batch_transform_vehicle_status([
            {"robot_id": "4F403", "latitude": 1.0, "longitude": 2.0, "timestamp": datetime.utcnow()},
            {"robot_id": "4E006", "latitude": 3.0, "longitude": 4.0, "timestamp": datetime.utcnow()}
        ])
        assert len(statuses) == 2
        assert len({s.device_id for s in statuses}) == 2

    def test_get_event_types_for_state(self):
        assert self.transformer._get_event_types_for_state(VehicleState.AVAILABLE) == ["service_start"]
        assert self.transformer._get_event_types_for_state(VehicleState.ON_TRIP) == ["trip_start"]
        assert self.transformer._get_event_types_for_state(VehicleState.NON_CONTACTABLE) == ["comms_lost"]

    def test_generate_trip_id(self):
        trip_data = {"job_id": "test-job-123"}
        trip_id = self.transformer._generate_trip_id(trip_data)
        assert isinstance(trip_id, UUID)
        assert trip_id == self.transformer._generate_trip_id(trip_data)