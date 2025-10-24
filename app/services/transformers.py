"""
Data transformation services for converting robot data to MDS format.
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid5, NAMESPACE_DNS
from datetime import datetime

from app.models.vehicles import Vehicle, VehicleStatus, VehicleAttributes, AccessibilityAttributes
from app.models.common import (
    VehicleState, GeoJSONFeature, GeoJSONPoint,
    VehicleType, PropulsionType, EventType
)
from app.config import settings

logger = logging.getLogger(__name__)


class DataTransformer:
    """Transform robot data to MDS-compliant format."""

    def __init__(self):
        """Initialize transformer with provider settings."""
        self.provider_id = settings.PROVIDER_ID_UUID

    def robot_id_to_device_id(self, robot_id: str) -> UUID:
        """
        Convert robot ID string to UUID device_id.

        Args:
            robot_id: Robot identifier string

        Returns:
            UUID device_id for MDS compliance
        """
        # Create deterministic UUID from robot_id using namespace
        return uuid5(NAMESPACE_DNS, f"{self.provider_id}.{robot_id}")

    def determine_vehicle_state(self, location_data: Dict[str, Any]) -> VehicleState:
        """
        Determine vehicle state based on robot location and activity data.

        Args:
            location_data: Robot location data from BigQuery

        Returns:
            MDS vehicle state
        """
        # For now, use simple logic based on data recency
        # In production, this would integrate with robot status systems

        timestamp = location_data.get('timestamp')
        if not timestamp:
            return VehicleState.MISSING

        # Convert timestamp to datetime if it's a string
        if isinstance(timestamp, str):
            try:
                location_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                return VehicleState.NON_CONTACTABLE
        else:
            location_time = timestamp

        now = datetime.utcnow()
        time_diff = (now - location_time.replace(tzinfo=None)).total_seconds()

        # Simple state logic - enhance with actual robot status data
        if time_diff > 3600:  # More than 1 hour old
            return VehicleState.NON_CONTACTABLE
        elif time_diff > 300:  # More than 5 minutes old
            return VehicleState.NON_OPERATIONAL
        else:
            return VehicleState.AVAILABLE  # Default to available for recent data

    def transform_location_to_geojson(self, lat: float, lng: float) -> GeoJSONFeature:
        """
        Transform lat/lng coordinates to GeoJSON Feature.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            GeoJSON Feature with Point geometry
        """
        return GeoJSONFeature(
            type="Feature",
            geometry=GeoJSONPoint(
                type="Point",
                coordinates=[lng, lat]  # GeoJSON is [longitude, latitude]
            ),
            properties={}
        )

    def get_robot_model_from_id(self, robot_id: str) -> str:
        """
        Determine robot model based on robot_id following the specified pattern.
        
        Args:
            robot_id: Robot identifier string
            
        Returns:
            Robot model string
        """
        try:
            # Extract prefix and number from robot_id
            # Assuming robot_id format like "4A001", "4B123", etc.
            if len(robot_id) >= 3:
                prefix = robot_id[:2]  # First 2 characters
                number_str = robot_id[2:]  # Rest of the string
                
                # Try to extract number from the string
                number = None
                for i, char in enumerate(number_str):
                    if not char.isdigit():
                        number = int(number_str[:i]) if i > 0 else None
                        break
                else:
                    number = int(number_str)
                
                if number is not None:
                    # Apply the model determination logic
                    if prefix == "4A" and 1 <= number <= 30:
                        return "Kiwibot 4.0"
                    elif prefix == "4B" and 1 <= number <= 120:
                        return "Kiwibot 4.1A"
                    elif prefix == "4C" and 1 <= number <= 100:
                        return "Kiwibot 4.1B"
                    elif prefix == "4D" and 1 <= number <= 300:
                        return "Kiwibot 4.2A"
                    elif prefix == "4E" and 1 <= number <= 120:
                        return "Kiwibot 4.3B"
                    elif prefix == "4E" and 121 <= number <= 130:
                        return "Kiwibot 4.3C"
                    elif prefix == "4E" and 200 <= number <= 290:
                        return "Kiwibot 4.3C"
                    elif prefix == "4F" and 1 <= number <= 262:
                        return "Kiwibot 4.3D"
                    elif prefix == "4F" and 301 <= number <= 322:
                        return "Kiwibot 4.3E"
                    elif prefix == "4F" and 401 <= number <= 410:
                        return "Kiwibot 4.3F"
                    elif prefix == "4G" and 1 <= number <= 5:
                        return "Kiwibot 4.3G"
                    elif prefix == "4H" and 1 <= number <= 81:
                        return "Kiwibot 4.4A"
            
            return "Unknown Version"
        except (ValueError, IndexError):
            return "Unknown Version"

    def transform_robot_to_vehicle(self, robot_data: Dict[str, Any]) -> Vehicle:
        """
        Transform robot data to MDS Vehicle model.

        Args:
            robot_data: Robot data from various sources

        Returns:
            MDS Vehicle object
        """
        robot_id = robot_data.get('robot_id')
        if not robot_id:
            raise ValueError("Robot data missing robot_id")

        device_id = self.robot_id_to_device_id(robot_id)
        
        # Determine robot model based on robot_id
        robot_model = self.get_robot_model_from_id(robot_id)

        # Create vehicle attributes based on robot properties
        vehicle_attributes = VehicleAttributes(
            year=2025,  # Updated to 2025 as requested
            make="Kiwibot",
            model=robot_model,  # Use determined model
            color="Blue",  # Updated to blue as requested
            equipped_cameras=4,  # Typical Kiwibot configuration
            wheel_count=4,
            width=0.6,  # Approximate Kiwibot dimensions
            length=0.8,
            height=0.6,
            weight=50,  # Approximate weight in kg
            top_speed=1.5,  # Max speed in m/s
            storage_capacity=30000  # 30L in cubic centimeters
        )

        # Accessibility features
        accessibility_attributes = AccessibilityAttributes(
            audio_cue=True,
            visual_cue=True,
            remote_open=True
        )

        return Vehicle(
            device_id=device_id,
            vehicle_id=str(device_id),  # Convert UUID to string per MDS spec
            provider_id=settings.PROVIDER_ID_UUID,
            vehicle_type=VehicleType.DELIVERY_ROBOT,
            propulsion_types=[PropulsionType.ELECTRIC],
            vehicle_attributes=vehicle_attributes,
            accessibility_attributes=[accessibility_attributes]  # Make it a list
        )

    def transform_location_to_vehicle_status(
        self,
        location_data: Dict[str, Any],
        trip_data: Optional[List[Dict[str, Any]]] = None
    ) -> VehicleStatus:
        """
        Transform robot location data to MDS VehicleStatus.

        Args:
            location_data: Robot location data from BigQuery
            trip_data: Optional active trip data

        Returns:
            MDS VehicleStatus object
        """
        robot_id = location_data.get('robot_id')
        if not robot_id:
            raise ValueError("Location data missing robot_id")

        device_id = self.robot_id_to_device_id(robot_id)

        # Determine vehicle state
        vehicle_state = self.determine_vehicle_state(location_data)

        # Convert timestamp to milliseconds
        timestamp = location_data.get('timestamp')
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            dt = timestamp
        last_event_time = int(dt.timestamp() * 1000)

        # Create location GeoJSON
        lat = location_data.get('latitude')
        lng = location_data.get('longitude')
        current_location = None
        if lat is not None and lng is not None:
            current_location = self.transform_location_to_geojson(lat, lng)

        # Determine event types based on state
        last_event_types = self._get_event_types_for_state(vehicle_state)

        # Extract active trip IDs
        trip_ids = []
        if trip_data:
            trip_ids = [self._generate_trip_id(trip) for trip in trip_data]

        return VehicleStatus(
            device_id=device_id,
            provider_id=settings.PROVIDER_ID_UUID,
            vehicle_state=vehicle_state,
            last_event_time=last_event_time,
            last_event_types=last_event_types,
            current_location=current_location,
            trip_ids=trip_ids if trip_ids else None
        )

    def _get_event_types_for_state(self, state: VehicleState) -> List[str]:
        """Get appropriate event types for a vehicle state."""
        event_mapping = {
            VehicleState.AVAILABLE: [EventType.SERVICE_START.value],
            VehicleState.NON_OPERATIONAL: [EventType.SERVICE_END.value],
            VehicleState.ON_TRIP: [EventType.TRIP_START.value],
            VehicleState.STOPPED: [EventType.TRIP_PAUSE.value],
            VehicleState.NON_CONTACTABLE: [EventType.COMMS_LOST.value],
            VehicleState.MISSING: [EventType.NOT_LOCATED.value],
            VehicleState.ELSEWHERE: [EventType.TRIP_LEAVE_JURISDICTION.value],
            VehicleState.RESERVED: [EventType.RESERVATION_START.value],
            VehicleState.REMOVED: [EventType.DECOMMISSIONED.value]
        }
        return event_mapping.get(state, [EventType.SERVICE_START.value])

    def _generate_trip_id(self, trip_data: Dict[str, Any]) -> UUID:
        """Generate UUID for trip based on job data."""
        job_id = trip_data.get('job_id', trip_data.get('id', ''))
        return uuid5(NAMESPACE_DNS, f"{self.provider_id}.trip.{job_id}")

    def _generate_event_id(self, event_data: Dict[str, Any]) -> UUID:
        """Generate UUID for event based on event data."""
        robot_id = event_data.get('robot_id', '')
        event_time = event_data.get('event_time', '')
        event_type = event_data.get('event_type', '')
        return uuid5(NAMESPACE_DNS, f"{self.provider_id}.event.{robot_id}.{event_time}.{event_type}")

    def batch_transform_vehicles(self, robot_data_list: List[Dict[str, Any]]) -> List[Vehicle]:
        """
        Transform multiple robots to Vehicle objects.

        Args:
            robot_data_list: List of robot data dictionaries

        Returns:
            List of MDS Vehicle objects
        """
        vehicles = []
        for robot_data in robot_data_list:
            try:
                vehicle = self.transform_robot_to_vehicle(robot_data)
                vehicles.append(vehicle)
            except Exception as e:
                logger.error(f"Failed to transform robot {robot_data.get('robot_id')}: {str(e)}")
                continue
        return vehicles

    def batch_transform_vehicle_status(
        self,
        location_data_list: List[Dict[str, Any]],
        trips_by_robot: Optional[Dict[str, List[Dict[str, Any]]]] = None
    ) -> List[VehicleStatus]:
        """
        Transform multiple location records to VehicleStatus objects.

        Args:
            location_data_list: List of location data dictionaries
            trips_by_robot: Optional mapping of robot_id to active trips

        Returns:
            List of MDS VehicleStatus objects
        """
        statuses = []
        trips_by_robot = trips_by_robot or {}

        for location_data in location_data_list:
            try:
                robot_id = location_data.get('robot_id')
                trip_data = trips_by_robot.get(robot_id, [])

                status = self.transform_location_to_vehicle_status(location_data, trip_data)
                statuses.append(status)
            except Exception as e:
                logger.error(f"Failed to transform location for robot {location_data.get('robot_id')}: {str(e)}")
                continue

        return statuses


# Global transformer instance
data_transformer = DataTransformer()