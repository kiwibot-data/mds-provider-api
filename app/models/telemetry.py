"""
Telemetry-related Pydantic models for MDS Provider API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from uuid import UUID
from datetime import datetime

from app.models.common import MDSResponse


class GPS(BaseModel):
    """GPS data for telemetry points."""
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    heading: Optional[float] = Field(None, description="Heading in degrees")
    speed: Optional[float] = Field(None, description="Speed in meters per second")
    accuracy: Optional[float] = Field(None, description="GPS accuracy in meters")
    hdop: Optional[float] = Field(None, description="Horizontal dilution of precision")

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


class Telemetry(BaseModel):
    """Telemetry model for vehicle GPS data."""
    device_id: UUID = Field(..., description="Unique device identifier")
    timestamp: int = Field(..., description="Timestamp when GPS data was recorded (milliseconds)")
    gps: GPS = Field(..., description="GPS coordinates and metadata")


class TelemetryResponse(MDSResponse):
    """Response model for /telemetry endpoint."""
    telemetry: List[Telemetry] = Field(..., description="Array of telemetry objects")
