"""
Vehicle-related Pydantic models for MDS Provider API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

from app.models.common import (
    MDSResponse, PaginationLinks, GeoJSONFeature, VehicleState
)


class VehicleAttributes(BaseModel):
    """Relatively static vehicle specification attributes (nested object)."""
    year: Optional[int] = Field(None, description="Year of manufacture")
    make: Optional[str] = Field(None, description="Manufacturer name")
    model: Optional[str] = Field(None, description="Model name")
    color: Optional[str] = Field(None, description="Vehicle color")
    inspection_date: Optional[str] = Field(None, description="Date of last inspection (YYYY-MM-DD)")
    equipped_cameras: Optional[int] = Field(None, description="Number of cameras equipped")
    equipped_lighting: Optional[str] = Field(None, description="Lighting configuration")
    wheel_count: Optional[int] = Field(None, description="Number of wheels")
    width: Optional[float] = Field(None, description="Vehicle width in meters")
    length: Optional[float] = Field(None, description="Vehicle length in meters")
    height: Optional[float] = Field(None, description="Vehicle height in meters")
    weight: Optional[float] = Field(None, description="Vehicle weight in kilograms")
    top_speed: Optional[float] = Field(None, description="Top speed in meters/second")
    storage_capacity: Optional[int] = Field(None, description="Storage capacity in cubic centimeters (cc)")

    class Config:
        extra = "forbid"


class AccessibilityAttributes(BaseModel):
    """Accessibility features object (was previously incorrectly modeled as an array)."""
    audio_cue: Optional[bool] = Field(None, description="Provides audio cues")
    visual_cue: Optional[bool] = Field(None, description="Provides visual cues")
    remote_open: Optional[bool] = Field(None, description="Remote compartment opening supported")


class Vehicle(BaseModel):
    """Vehicle information model - updated for MDS 2.0 compliance (delivery robots)."""
    # Core identity
    device_id: UUID = Field(..., description="Unique device identifier")
    provider_id: str = Field(..., description="Provider identifier (string per spec)")
    vehicle_id: Optional[str] = Field(None, description="Internal vehicle identifier (optional)")

    # Classification
    vehicle_type: str = Field("robot", description="Vehicle type (MDS delivery robot)")
    propulsion_types: List[str] = Field(..., min_items=1, description="Propulsion types (e.g. electric)")

    # Top‑level descriptive attributes (moved out of vehicle_attributes per spec example)
    year: Optional[int] = Field(None, description="Year of manufacture")
    mfgr: Optional[str] = Field(None, description="Manufacturer name")
    model: Optional[str] = Field(None, description="Model name")

    # Nested attribute objects
    vehicle_attributes: Optional[VehicleAttributes] = Field(None, description="Extended vehicle specification attributes")
    accessibility_attributes: Optional[AccessibilityAttributes] = Field(None, description="Accessibility feature flags")

    # Optional metadata
    data_provider_id: Optional[UUID] = Field(None, description="Optional data provider identifier")
    last_reported: Optional[int] = Field(None, description="Last time vehicle reported (milliseconds)")

    class Config:
        use_enum_values = True


class VehicleStatus(BaseModel):
    """Vehicle status model for real-time monitoring - MDS 2.0 compliant."""
    # Required fields per MDS 2.0
    device_id: UUID = Field(..., description="Unique device identifier")
    provider_id: str = Field(..., description="Provider identifier (string)")
    vehicle_state: VehicleState = Field(..., description="Current vehicle state")
    last_event_time: int = Field(..., description="Timestamp of last state change (milliseconds)")
    last_event_types: List[str] = Field(..., min_items=1, description="Event types that caused last state change")
    last_event: Optional[Dict[str, Any]] = Field(None, description="Last event object")
    last_telemetry: Optional[Dict[str, Any]] = Field(None, description="Last telemetry object")

    # Optional fields per MDS 2.0 spec
    data_provider_id: Optional[UUID] = Field(None, description="Optional data provider identifier")
    last_vehicle_state: Optional[VehicleState] = Field(None, description="Previous vehicle state")
    current_location: Optional[GeoJSONFeature] = Field(None, description="Current vehicle location")
    trip_ids: Optional[List[UUID]] = Field(None, description="Active trip IDs")

    class Config:
        use_enum_values = True


class VehiclesResponse(MDSResponse):
    """Response model for /vehicles endpoint."""
    vehicles: List[Vehicle] = Field(..., description="Array of vehicle objects")
    last_updated: int = Field(..., description="Timestamp when data was last updated (milliseconds)")
    ttl: int = Field(..., description="Time to live for this data (milliseconds)")
    links: Optional[List[Dict[str, str]]] = Field(None, description="Pagination links")


class VehicleStatusResponse(MDSResponse):
    """Response model for /vehicles/status endpoint."""
    vehicles_status: List[VehicleStatus] = Field(..., description="Array of vehicle status objects")
    last_updated: int = Field(..., description="Timestamp when data was last updated (milliseconds)")
    ttl: int = Field(..., description="Time to live for this data (milliseconds)")
    links: Optional[Dict[str, str]] = Field(None, description="Pagination links")