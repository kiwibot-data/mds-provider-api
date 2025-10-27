"""
Telemetry-related Pydantic models for MDS Provider API.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator
from uuid import UUID

from app.models.common import MDSResponse


class GPS(BaseModel):
    """GPS data for telemetry and event locations - MDS 2.0 compliant."""
    # Required fields
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees (WGS 84)")
    lng: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees (WGS 84)")

    # Optional fields per MDS 2.0 spec
    altitude: Optional[float] = Field(None, description="Altitude above mean sea level in meters")
    heading: Optional[float] = Field(None, ge=0, le=360, description="Heading in degrees (0-360, clockwise from true North)")
    speed: Optional[float] = Field(None, description="Speed in meters per second")
    horizontal_accuracy: Optional[float] = Field(None, description="Horizontal accuracy in meters")
    vertical_accuracy: Optional[float] = Field(None, description="Vertical accuracy in meters")
    satellites: Optional[int] = Field(None, ge=0, description="Number of GPS/GNSS satellites")

    @validator("lat")
    def validate_latitude(cls, v):
        if not (-90 <= v <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @validator("lng")
    def validate_longitude(cls, v):
        if not (-180 <= v <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v

    @validator("heading")
    def validate_heading(cls, v):
        if v is not None and not (0 <= v <= 360):
            raise ValueError("Heading must be between 0 and 360 degrees")
        return v

    @validator("satellites")
    def validate_satellites(cls, v):
        if v is not None and v < 0:
            raise ValueError("Satellites must be >= 0")
        return v


class Telemetry(BaseModel):
    """Telemetry model for vehicle GPS data - MDS 2.0 compliant."""
    # Required fields per MDS 2.0 spec
    provider_id: UUID = Field(..., description="Provider identifier (UUID)")
    device_id: UUID = Field(..., description="Unique device identifier")
    telemetry_id: UUID = Field(..., description="Unique telemetry point identifier")
    timestamp: int = Field(..., description="Timestamp when GPS data was recorded (milliseconds since epoch)")
    trip_ids: List[UUID] = Field(..., min_items=1, description="IDs of trips during which telemetry occurred")
    journey_id: UUID = Field(..., description="Unique journey identifier")
    location: GPS = Field(..., description="GPS coordinates and metadata")

    # Optional fields per MDS 2.0 spec
    data_provider_id: Optional[UUID] = Field(None, description="Optional data provider identifier")
    stop_id: Optional[UUID] = Field(None, description="Stop identifier if at a stop")
    location_type: Optional[str] = Field(None, description="Type of location (street, sidewalk, crosswalk, garage, bike_lane)")
    battery_percent: Optional[int] = Field(None, ge=0, le=100, description="Battery percentage 0-100")
    fuel_percent: Optional[int] = Field(None, ge=0, le=100, description="Fuel percentage 0-100")

    @validator('trip_ids')
    def validate_trip_ids(cls, v):
        """Ensure trip_ids has at least one item and all items are unique."""
        if not v or len(v) < 1:
            raise ValueError("trip_ids must contain at least one trip ID")
        if len(v) != len(set(v)):
            raise ValueError("trip_ids must contain unique values")
        return v

    class Config:
        use_enum_values = True


class TelemetryResponse(MDSResponse):
    """Response model for /telemetry endpoint."""
    telemetry: List[Telemetry] = Field(..., description="Array of telemetry objects")
