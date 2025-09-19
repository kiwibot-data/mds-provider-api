"""
Event-related Pydantic models for MDS Provider API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

from app.models.common import (
    MDSResponse, PaginationLinks, GeoJSONFeature, VehicleState, EventType
)


class Event(BaseModel):
    """Event model for delivery robot state changes."""
    provider_id: str = Field(..., description="Provider identifier")
    device_id: UUID = Field(..., description="Unique device identifier")
    event_types: List[EventType] = Field(..., description="Event types that occurred")
    vehicle_state: VehicleState = Field(..., description="Vehicle state after the event")
    event_time: int = Field(..., description="When the event occurred (milliseconds)")
    publication_time: Optional[int] = Field(None, description="When event was published (milliseconds)")
    event_location: Optional[GeoJSONFeature] = Field(None, description="Location where event occurred")
    battery_pct: Optional[float] = Field(None, description="Battery percentage (not used for delivery robots)")
    trip_id: Optional[UUID] = Field(None, description="Associated trip ID if applicable")
    associated_ticket: Optional[str] = Field(None, description="Associated support ticket")


class EventsResponse(MDSResponse):
    """Response model for /events endpoints."""
    events: List[Event] = Field(..., description="Array of event objects")
    links: Optional[PaginationLinks] = Field(None, description="Pagination links")


class RealtimeEventsResponse(MDSResponse):
    """Response model for /events/recent endpoint."""
    events: List[Event] = Field(..., description="Array of event objects")
    last_updated: int = Field(..., description="Timestamp when data was last updated (milliseconds)")
    ttl: int = Field(..., description="Time to live for this data (milliseconds)")