"""
Event-related Pydantic models for MDS Provider API.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator, ConfigDict
from uuid import UUID

from app.models.common import (
    MDSResponse, VehicleState, EventType
)
from app.models.telemetry import GPS


class Event(BaseModel):
    """Event model for delivery robot state changes - MDS 2.0 compliant."""
    # Required fields
    event_id: UUID = Field(..., description="Unique event identifier")
    provider_id: UUID = Field(..., description="Provider identifier UUID")
    device_id: UUID = Field(..., description="Unique device identifier")
    event_types: List[EventType] = Field(..., min_items=1, description="Event types that occurred")
    vehicle_state: VehicleState = Field(..., description="Vehicle state after the event")
    timestamp: int = Field(..., description="When the event occurred (milliseconds since epoch)")

    # Optional fields per MDS 2.0 spec
    data_provider_id: Optional[str] = Field(None, description="Optional data provider identifier")
    publication_time: Optional[int] = Field(None, description="When event was published (milliseconds)")
    location: Optional[GPS] = Field(None, description="GPS location where event occurred")
    event_geographies: Optional[List[UUID]] = Field(None, description="Geography UUIDs where event occurred")
    battery_percent: Optional[int] = Field(None, ge=0, le=100, description="Battery percentage 0-100 (integer)")
    fuel_percent: Optional[int] = Field(None, ge=0, le=100, description="Fuel percentage 0-100 (integer)")
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

    @validator('event_geographies', always=True)
    def validate_location_or_geography(cls, v, values):
        """Ensure either location or event_geographies is provided (MDS 2.0 requirement)."""
        location = values.get('location')
        if not location and not v:
            raise ValueError("Either 'location' or 'event_geographies' must be provided")
        return v

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        exclude_none=True  # Exclude None values from JSON serialization
    )


class EventsResponse(MDSResponse):
    """Response model for /events endpoints."""
    events: List[Event] = Field(..., description="Array of event objects")

    model_config = ConfigDict(
        exclude_none=True  # Exclude None values from JSON serialization
    )


class RealtimeEventsResponse(MDSResponse):
    """Response model for /events/recent endpoint."""
    events: List[Event] = Field(..., description="Array of event objects")
    # Note: last_updated and ttl are NOT part of MDS 2.0 schema for /events/recent
    # The schema only allows 'version' and 'events' fields

    model_config = ConfigDict(
        exclude_none=True  # Exclude None values from JSON serialization
    )