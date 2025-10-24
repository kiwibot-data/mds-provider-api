"""
Event-related Pydantic models for MDS Provider API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from uuid import UUID
from datetime import datetime

from app.models.common import (
    MDSResponse, PaginationLinks, GeoJSONFeature, VehicleState, EventType
)


class Event(BaseModel):
    """Event model for delivery robot state changes - MDS 2.0 compliant."""
    # Required fields
    event_id: UUID = Field(..., description="Unique event identifier")
    provider_id: UUID = Field(..., description="Provider identifier (UUID)")
    device_id: UUID = Field(..., description="Unique device identifier")
    event_types: List[EventType] = Field(..., min_items=1, description="Event types that occurred")
    vehicle_state: VehicleState = Field(..., description="Vehicle state after the event")
    timestamp: int = Field(..., description="When the event occurred (milliseconds since epoch)")

    # Optional fields per MDS 2.0 spec
    data_provider_id: Optional[UUID] = Field(None, description="Optional data provider identifier")
    publication_time: Optional[int] = Field(None, description="When event was published (milliseconds)")
    location: Optional["GPS"] = Field(None, description="GPS location where event occurred")
    event_geographies: Optional[List[UUID]] = Field(None, description="Geography UUIDs where event occurred")
    battery_pct: Optional[float] = Field(None, ge=0, le=100, description="Battery percentage 0-100")
    fuel_percent: Optional[float] = Field(None, ge=0, le=100, description="Fuel percentage 0-100")
    trip_ids: Optional[List[UUID]] = Field(None, description="Associated trip IDs if applicable")
    associated_ticket: Optional[str] = Field(None, description="Associated support ticket")

    @validator('event_types')
    def validate_event_types(cls, v):
        """Ensure event_types has at least one item and all items are unique."""
        if not v or len(v) < 1:
            raise ValueError("event_types must contain at least one event type")
        if len(v) != len(set(v)):
            raise ValueError("event_types must contain unique values")
        return v

    class Config:
        use_enum_values = True


# Import GPS for type hint
from app.models.telemetry import GPS
Event.update_forward_refs()


class EventsResponse(MDSResponse):
    """Response model for /events endpoints."""
    events: List[Event] = Field(..., description="Array of event objects")


class RealtimeEventsResponse(MDSResponse):
    """Response model for /events/recent endpoint."""
    events: List[Event] = Field(..., description="Array of event objects")