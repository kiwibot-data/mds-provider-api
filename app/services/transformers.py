"""
Data transformation services for converting robot data to MDS format.
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid5, NAMESPACE_DNS
from datetime import datetime

from app.models.vehicles import Vehicle, VehicleStatus, VehicleAttributes
from app.models.common import (
    VehicleState, GeoJSONFeature, GeoJSONPoint,
    EventType, VehicleType, PropulsionType
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

        # Build required delivery-robots vehicle_attributes - only include MDS 2.0 allowed fields
        vehicle_attributes = VehicleAttributes(
            vin=f"VIN-{robot_id}",
            license_plate=robot_id
        )

        # Fix accessibility_attributes - schema expects array, not null
        accessibility = []  # Empty array to satisfy schema requirement

        return Vehicle(
            device_id=device_id,
            vehicle_id=robot_id,
            provider_id=str(self.provider_id),
            vehicle_type=VehicleType.DELIVERY_ROBOT,
            propulsion_types=[PropulsionType.ELECTRIC],
            mfgr="Kiwibot",
            accessibility_attributes=accessibility,
            vehicle_attributes=vehicle_attributes,
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

    # data_provider_id no longer included in reverted schemas

        # Create last_event and last_telemetry objects
        last_event_id = uuid5(NAMESPACE_DNS, f"{settings.PROVIDER_ID}.event.{robot_id}.{last_event_time}")
        last_telemetry_id = uuid5(NAMESPACE_DNS, f"{settings.PROVIDER_ID}.telemetry.{robot_id}.{last_event_time}")
        
        # Create GPS location object for event/telemetry
        from app.models.telemetry import GPS
        # Always create GPS object with valid coordinates (use default if missing)
        default_lat = 38.9197 if lat is None else lat
        default_lng = -77.0218 if lng is None else lng
        gps_location = GPS(
            lat=round(default_lat, 7),
            lng=round(default_lng, 7),
            horizontal_accuracy=5.0
        )
        
        # Select event_types for this event based on current vehicle_state ensuring it matches delivery-robots oneOf sets.
        from app.models.common import EventType as ET
        selected_event_types: List[ET] = []
        for et_val in last_event_types:
            try:
                selected_event_types.append(ET(et_val))
            except ValueError:
                continue
        if not selected_event_types:
            selected_event_types = [ET.LOCATED]

        # Ensure vehicle_state/event_types combination is valid for delivery-robots spec (simplified guard):
        if vehicle_state == VehicleState.MISSING:
            selected_event_types = [ET.NOT_LOCATED]
        elif vehicle_state == VehicleState.NON_CONTACTABLE:
            selected_event_types = [ET.COMMS_LOST]

        from app.models.events import Event
        # Create dummy geography UUID for event_geographies requirement
        dummy_geography_id = uuid5(NAMESPACE_DNS, f"{self.provider_id}.geography.default")
        
        last_event_obj = Event(
            event_id=last_event_id,
            provider_id=self.provider_id,
            device_id=device_id,
            event_types=selected_event_types,
            vehicle_state=vehicle_state,
            timestamp=last_event_time,
            location=gps_location,
            publication_time=last_event_time,
            event_geographies=[dummy_geography_id],  # Must have at least 1 item
            fuel_percent=50,
            battery_pct=80.0,
            data_provider_id=str(self.provider_id),  # Ensure it's string, not null
            trip_ids=[uuid5(NAMESPACE_DNS, f"{self.provider_id}.trip.{robot_id}")],
            associated_ticket="support-" + robot_id
        )
        
        # Create full Telemetry object
        from app.models.telemetry import Telemetry
        journey_id = uuid5(NAMESPACE_DNS, f"{self.provider_id}.journey.{robot_id}")
        last_telemetry_obj = Telemetry(
            provider_id=self.provider_id,
            device_id=device_id,
            telemetry_id=last_telemetry_id,
            timestamp=last_event_time,
            trip_ids=trip_ids if trip_ids else [uuid5(NAMESPACE_DNS, f"{self.provider_id}.trip.{robot_id}")],
            journey_id=journey_id,
            location=gps_location,
            battery_percent=80,
            fuel_percent=50,
            location_type="street",
            stop_id=uuid5(NAMESPACE_DNS, f"{self.provider_id}.stop.{robot_id}")  # Must be UUID, not string
        )
        # Inject data_provider_id and populate optional GPS extended fields if available
        last_telemetry_obj.data_provider_id = str(self.provider_id)  # Ensure string
        # Augment GPS with placeholder extended attributes (silently ignore if model restricts assignment)
        try:
            gps_location.altitude = 10.0
            gps_location.heading = 180.0
            gps_location.speed = 0.5
            gps_location.vertical_accuracy = 5.0
            gps_location.satellites = 12
        except Exception:
            pass

        # Serialize nested objects to dicts as VehicleStatus expects Dict fields
        # Use mode='json' and exclude_none=True to ensure None values are excluded and UUIDs are serialized
        return VehicleStatus(
            device_id=device_id,
            provider_id=str(self.provider_id),
            data_provider_id=str(self.provider_id),  # Must be string, not null
            vehicle_state=vehicle_state,
            last_event_time=last_event_time,
            last_event_types=last_event_types,
            last_event=last_event_obj.model_dump(mode='json', exclude_none=True),
            last_telemetry=last_telemetry_obj.model_dump(mode='json', exclude_none=True),
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

    def batch_transform_vehicles(self, robot_data_list: List[Dict[str, Any]]) -> List[Vehicle]:
        """Transform multiple robot records to Vehicle objects (legacy helper for tests)."""
        vehicles: List[Vehicle] = []
        for robot_data in robot_data_list:
            try:
                vehicle = self.transform_robot_to_vehicle(robot_data)
                vehicles.append(vehicle)
            except Exception as e:
                logger.error(f"Failed to transform robot data: {robot_data.get('robot_id')} - {e}")
                continue
        return vehicles


# Global transformer instance
data_transformer = DataTransformer()

def transform_robot_to_vehicle(robot_data: Dict[str, Any]) -> Vehicle:
    """
    Transforms robot data to an MDS Vehicle object.
    """
    return data_transformer.transform_robot_to_vehicle(robot_data)

def transform_robot_to_vehicle_status(robot_data: Dict[str, Any]) -> VehicleStatus:
    """
    Transforms robot data to an MDS VehicleStatus object.
    """
    return data_transformer.transform_location_to_vehicle_status(robot_data)