"""
Trip-related Pydantic models for MDS Provider API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

from app.models.common import (
    MDSResponse, GeoJSONFeature, TripType, DriverType
)


class JourneyAttributes(BaseModel):
    """Journey attributes - not used in delivery robots mode."""
    pass


class TripAttributes(BaseModel):
    """Trip attributes specific to delivery robots."""
    driver_type: DriverType = Field(..., description="Type of driver operating the device")
    driver_id: Optional[UUID] = Field(None, description="Unique identifier of the primary driver")
    app_name: Optional[str] = Field(None, description="Name of app used to reserve the trip")
    requested_time: Optional[int] = Field(None, description="When customer requested the trip (milliseconds)")
    has_payload: Optional[bool] = Field(None, description="Is there payload for delivery at trip start")
    range: Optional[int] = Field(None, description="Estimated range in meters at trip start")
    identification_required: Optional[bool] = Field(None, description="Does cargo require customer ID")


class FareAttributes(BaseModel):
    """Fare attributes for delivery trips."""
    payment_type: Optional[str] = Field(None, description="Payment method used")
    price: Optional[float] = Field(None, description="Total price of the order")


class Trip(BaseModel):
    """Trip model for delivery robots."""
    provider_id: str = Field(..., description="Provider identifier")
    device_id: UUID = Field(..., description="Unique device identifier")
    trip_id: UUID = Field(..., description="Unique trip identifier")
    trip_duration: int = Field(..., description="Trip duration in seconds")
    trip_distance: Optional[int] = Field(None, description="Trip distance in meters")
    route: GeoJSONFeature = Field(..., description="Trip route as GeoJSON LineString")
    accuracy: Optional[int] = Field(None, description="GPS accuracy in meters")
    start_time: int = Field(..., description="Trip start time (milliseconds)")
    end_time: int = Field(..., description="Trip end time (milliseconds)")
    publication_time: Optional[int] = Field(None, description="When trip data was published")
    parking_verification_url: Optional[str] = Field(None, description="URL for parking verification")
    standard_cost: Optional[int] = Field(None, description="Standard cost in cents")
    actual_cost: Optional[int] = Field(None, description="Actual cost in cents")
    trip_type: TripType = Field(TripType.DELIVERY, description="Type of trip")
    journey_id: Optional[UUID] = Field(None, description="Journey identifier for overlapping trips")
    journey_attributes: Optional[JourneyAttributes] = Field(None, description="Journey attributes")
    trip_attributes: Optional[TripAttributes] = Field(None, description="Trip-specific attributes")
    fare_attributes: Optional[FareAttributes] = Field(None, description="Fare information")


class TripsResponse(MDSResponse):
    """Response model for /trips endpoint."""
    trips: List[Trip] = Field(..., description="Array of trip objects")