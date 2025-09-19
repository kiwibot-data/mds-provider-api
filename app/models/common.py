"""
Common Pydantic models for MDS Provider API.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from uuid import UUID
from datetime import datetime
from enum import Enum
from app.config import MDSConstants


class GeoJSONPoint(BaseModel):
    """GeoJSON Point geometry."""
    type: str = Field("Point", description="GeoJSON geometry type")
    coordinates: List[float] = Field(..., description="[longitude, latitude] coordinates")

    @validator("coordinates")
    def validate_coordinates(cls, v):
        if len(v) != 2:
            raise ValueError("Coordinates must contain exactly 2 values [longitude, latitude]")
        lng, lat = v
        if not (-180 <= lng <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        if not (-90 <= lat <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v


class GeoJSONLineString(BaseModel):
    """GeoJSON LineString geometry."""
    type: str = Field("LineString", description="GeoJSON geometry type")
    coordinates: List[List[float]] = Field(..., description="Array of [longitude, latitude] coordinates")

    @validator("coordinates")
    def validate_coordinates(cls, v):
        if len(v) < 2:
            raise ValueError("LineString must have at least 2 coordinate pairs")
        for coord in v:
            if len(coord) != 2:
                raise ValueError("Each coordinate must contain exactly 2 values [longitude, latitude]")
            lng, lat = coord
            if not (-180 <= lng <= 180):
                raise ValueError("Longitude must be between -180 and 180")
            if not (-90 <= lat <= 90):
                raise ValueError("Latitude must be between -90 and 90")
        return v


class GeoJSONFeature(BaseModel):
    """GeoJSON Feature object."""
    type: str = Field("Feature", description="GeoJSON object type")
    geometry: Union[GeoJSONPoint, GeoJSONLineString] = Field(..., description="GeoJSON geometry")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature properties")


class VehicleState(str, Enum):
    """Vehicle states for delivery robots."""
    REMOVED = "removed"
    AVAILABLE = "available"
    NON_OPERATIONAL = "non_operational"
    RESERVED = "reserved"
    ON_TRIP = "on_trip"
    STOPPED = "stopped"
    NON_CONTACTABLE = "non_contactable"
    MISSING = "missing"
    ELSEWHERE = "elsewhere"


class EventType(str, Enum):
    """Event types for delivery robots."""
    COMMS_LOST = "comms_lost"
    COMMS_RESTORED = "comms_restored"
    COMPLIANCE_PICK_UP = "compliance_pick_up"
    DECOMMISSIONED = "decommissioned"
    NOT_LOCATED = "not_located"
    LOCATED = "located"
    MAINTENANCE = "maintenance"
    MAINTENANCE_PICK_UP = "maintenance_pick_up"
    MAINTENANCE_END = "maintenance_end"
    DRIVER_CANCELLATION = "driver_cancellation"
    ORDER_DROP_OFF = "order_drop_off"
    ORDER_PICK_UP = "order_pick_up"
    CUSTOMER_CANCELLATION = "customer_cancellation"
    PROVIDER_CANCELLATION = "provider_cancellation"
    RECOMMISSION = "recommission"
    RESERVATION_START = "reservation_start"
    RESERVATION_STOP = "reservation_stop"
    SERVICE_END = "service_end"
    SERVICE_START = "service_start"
    TRIP_END = "trip_end"
    TRIP_ENTER_JURISDICTION = "trip_enter_jurisdiction"
    TRIP_LEAVE_JURISDICTION = "trip_leave_jurisdiction"
    TRIP_RESUME = "trip_resume"
    TRIP_START = "trip_start"
    TRIP_PAUSE = "trip_pause"


class TripType(str, Enum):
    """Trip types for delivery robots."""
    DELIVERY = "delivery"
    RETURN = "return"
    ADVERTISING = "advertising"
    MAPPING = "mapping"
    ROAMING = "roaming"


class DriverType(str, Enum):
    """Driver types for delivery robots."""
    HUMAN = "human"
    SEMI_AUTONOMOUS = "semi_autonomous"
    AUTONOMOUS = "autonomous"


class VehicleType(str, Enum):
    """Vehicle type for delivery robots."""
    ROBOT = "robot"


class PropulsionType(str, Enum):
    """Propulsion types for delivery robots."""
    ELECTRIC = "electric"


class PaginationLinks(BaseModel):
    """Pagination links following JSON API specification."""
    first: Optional[str] = Field(None, description="URL to first page")
    last: Optional[str] = Field(None, description="URL to last page")
    prev: Optional[str] = Field(None, description="URL to previous page")
    next: Optional[str] = Field(None, description="URL to next page")


class MDSResponse(BaseModel):
    """Base MDS response model."""
    version: str = Field(MDSConstants.CONTENT_TYPE_JSON.split("version=")[1], description="MDS version")

    class Config:
        json_encoders = {
            datetime: lambda v: int(v.timestamp() * 1000)  # Convert to milliseconds timestamp
        }