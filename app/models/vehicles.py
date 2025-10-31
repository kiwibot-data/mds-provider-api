"""
Vehicle-related Pydantic models for MDS Provider API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

from app.models.common import (
    MDSResponse, GeoJSONFeature, VehicleState, VehicleType, PropulsionType
)


class VehicleAttributes(BaseModel):
    """Delivery-robots vehicle_attributes subset per MDS 2.0 (strict schema compliance)."""
    vin: str = Field(..., description="VIN number")
    license_plate: str = Field(..., description="License plate number")

    class Config:
        extra = "forbid"


class AccessibilityAttributes(BaseModel):
    """Delivery-robots accessibility attributes object."""
    audio_cue: Optional[bool] = Field(None, description="Device equipped with audio cues")
    visual_cue: Optional[bool] = Field(None, description="Device equipped with visual cues")
    remote_open: Optional[bool] = Field(None, description="Remote door open capability")

    class Config:
        extra = "forbid"


class Vehicle(BaseModel):
    """Delivery-robots Vehicle model aligned with validator (object accessibility, required vehicle_attributes core)."""
    device_id: UUID = Field(..., description="Unique device identifier")
    provider_id: str = Field(..., description="Provider identifier string")
    vehicle_id: str = Field(..., description="Vehicle identifier (string, not UUID)")
    mfgr: str = Field("Kiwibot", description="Manufacturer (legacy field for tests)")
    vehicle_type: VehicleType = Field(VehicleType.DELIVERY_ROBOT, description="Vehicle type")
    @property
    def vehicle_type_str(self) -> str:
        return "robot" if self.vehicle_type == VehicleType.DELIVERY_ROBOT else str(self.vehicle_type)
    propulsion_types: List[PropulsionType] = Field(..., min_items=1, description="Propulsion types")
    accessibility_attributes: Optional[List[str]] = Field(None, description="Accessibility attributes as a list of strings")
    vehicle_attributes: VehicleAttributes = Field(..., description="Static vehicle attributes")
    last_reported: Optional[int] = Field(None, description="Last time vehicle reported (ms)")

    model_config = ConfigDict(
        exclude_none=True  # Exclude None values from JSON serialization
    )


class VehicleStatus(BaseModel):
    """Vehicle status model with nested Event & Telemetry objects as dicts."""
    device_id: UUID = Field(..., description="Unique device identifier")
    provider_id: str = Field(..., description="Provider identifier string")
    data_provider_id: Optional[str] = Field(None, description="Data provider identifier if different")
    vehicle_state: VehicleState = Field(..., description="Current vehicle state")
    last_event_time: int = Field(..., description="Timestamp of last state change (ms)")
    last_event_types: List[str] = Field(..., min_items=1, description="Event types causing last state change")
    last_event: Dict[str, Any] = Field(..., description="Last event object (required by spec)")
    last_telemetry: Dict[str, Any] = Field(..., description="Last telemetry object (required by spec)")
    current_location: Optional[GeoJSONFeature] = Field(None, description="Current vehicle location")
    trip_ids: Optional[List[UUID]] = Field(None, description="Active trip IDs")

    model_config = ConfigDict(
        exclude_none=True  # Exclude None values from JSON serialization
    )


class VehiclesResponse(MDSResponse):
    data: Dict[str, List[Vehicle]] = Field(..., description="Response data payload")


class VehicleStatusResponse(MDSResponse):
    data: Dict[str, List[VehicleStatus]] = Field(..., description="Response data payload")


class SpecificVehicleStatusResponse(MDSResponse):
    """Response model for a single vehicle's status, without pagination links."""
    data: Dict[str, VehicleStatus] = Field(..., description="Response data payload for a single vehicle status")


class VehicleEvent(BaseModel):
    """Vehicle event model."""
    device_id: UUID = Field(..., description="Unique device identifier")
    provider_id: str = Field(..., description="Provider identifier string")
    event_type: str = Field(..., description="Type of the event")
    event_time: int = Field(..., description="Timestamp of the event (ms)")
    event_data: Dict[str, Any] = Field(..., description="Event-specific data")