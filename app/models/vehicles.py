"""
Vehicle-related Pydantic models for MDS Provider API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

from app.models.common import (
    MDSResponse, PaginationLinks, GeoJSONFeature, VehicleState,
    VehicleType, PropulsionType
)


class VehicleAttributes(BaseModel):
    """Vehicle attributes specific to delivery robots."""
    year: Optional[int] = Field(None, description="Year of manufacture")
    make: Optional[str] = Field(None, description="Vehicle manufacturer")
    model: Optional[str] = Field(None, description="Vehicle model")
    color: Optional[str] = Field(None, description="Vehicle color")
    inspection_date: Optional[str] = Field(None, description="Date of last inspection (YYYY-MM-DD)")
    equipped_cameras: Optional[int] = Field(None, description="Number of cameras on device")
    equipped_lighting: Optional[int] = Field(None, description="Number of lights on device")
    wheel_count: Optional[int] = Field(None, description="Number of wheels")
    width: Optional[float] = Field(None, description="Width in meters")
    length: Optional[float] = Field(None, description="Length in meters")
    height: Optional[float] = Field(None, description="Height in meters")
    weight: Optional[float] = Field(None, description="Weight in kilograms")
    top_speed: Optional[float] = Field(None, description="Top speed in meters per second")
    storage_capacity: Optional[int] = Field(None, description="Cargo space in cubic centimeters")


class AccessibilityAttributes(BaseModel):
    """Accessibility attributes for delivery robots."""
    audio_cue: Optional[bool] = Field(None, description="Has audio cues upon delivery")
    visual_cue: Optional[bool] = Field(None, description="Has visual cues upon delivery")
    remote_open: Optional[bool] = Field(None, description="Can door be remotely opened")


class Vehicle(BaseModel):
    """Vehicle information model."""
    device_id: UUID = Field(..., description="Unique device identifier")
    vehicle_id: UUID = Field(..., description="Unique vehicle identifier (same as device_id)")
    provider_id: str = Field(..., description="Provider identifier (UUID)")
    vehicle_type: VehicleType = Field(VehicleType.DELIVERY_ROBOT, description="Vehicle type")
    propulsion_types: List[PropulsionType] = Field([PropulsionType.ELECTRIC], description="Propulsion types")
    vehicle_attributes: Optional[VehicleAttributes] = Field(None, description="Vehicle-specific attributes")
    accessibility_attributes: Optional[List[AccessibilityAttributes]] = Field(None, description="Accessibility features")


class VehicleStatus(BaseModel):
    """Vehicle status model for real-time monitoring."""
    device_id: UUID = Field(..., description="Unique device identifier")
    provider_id: str = Field(..., description="Provider identifier (UUID)")
    vehicle_state: VehicleState = Field(..., description="Current vehicle state")
    last_vehicle_state: Optional[VehicleState] = Field(None, description="Previous vehicle state")
    last_event_time: int = Field(..., description="Timestamp of last state change (milliseconds)")
    last_event_types: List[str] = Field(..., description="Event types that caused last state change")
    current_location: Optional[GeoJSONFeature] = Field(None, description="Current vehicle location")
    trip_ids: Optional[List[UUID]] = Field(None, description="Active trip IDs")


class VehiclesResponse(MDSResponse):
    """Response model for /vehicles endpoint."""
    vehicles: List[Vehicle] = Field(..., description="Array of vehicle objects")
    last_updated: int = Field(..., description="Timestamp when data was last updated (milliseconds)")
    ttl: int = Field(..., description="Time to live for this data (milliseconds)")
    links: Optional[PaginationLinks] = Field(None, description="Pagination links")


class VehicleStatusResponse(MDSResponse):
    """Response model for /vehicles/status endpoint."""
    vehicles_status: List[VehicleStatus] = Field(..., description="Array of vehicle status objects")
    last_updated: int = Field(..., description="Timestamp when data was last updated (milliseconds)")
    ttl: int = Field(..., description="Time to live for this data (milliseconds)")
    links: Optional[PaginationLinks] = Field(None, description="Pagination links")