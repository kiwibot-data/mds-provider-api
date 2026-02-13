"""
Trips endpoints for MDS Provider API.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Query, status

from app.models.trips import TripsResponse, Trip, TripAttributes, FareAttributes
from app.models.common import TripType, DriverType
from app.models.telemetry import GPS
import app.services.bigquery as bigquery_module
from app.services.transformers import data_transformer
from app.auth.middleware import get_current_provider_id
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def transform_trip_data_to_mds(trip_data: dict) -> Trip:
    """Transform BigQuery trip data to MDS Trip model."""
    robot_id = trip_data.get('robot_id')
    if not robot_id:
        raise ValueError("Trip data missing robot_id")

    device_id = data_transformer.robot_id_to_device_id(robot_id)
    trip_id = data_transformer._generate_trip_id(trip_data)

    # Extract timing data
    start_time = trip_data.get('trip_start')
    end_time = trip_data.get('trip_end')
    duration_seconds = trip_data.get('trip_duration_seconds', 0)

    # Convert timestamps
    if isinstance(start_time, datetime):
        start_time_ms = int(start_time.timestamp() * 1000)
    else:
        start_time_ms = int(start_time * 1000) if start_time else 0

    if isinstance(end_time, datetime):
        end_time_ms = int(end_time.timestamp() * 1000)
    else:
        end_time_ms = int(end_time * 1000) if end_time else 0

    # Create start and end location geometries
    start_lat = trip_data.get('start_latitude')
    start_lng = trip_data.get('start_longitude')
    end_lat = trip_data.get('end_latitude')
    end_lng = trip_data.get('end_longitude')

    if start_lat is None or start_lng is None:
        raise ValueError("Trip data missing start location coordinates")
    
    if end_lat is None or end_lng is None:
        raise ValueError("Trip data missing end location coordinates")

    # Create start and end location GPS objects (MDS 2.0 expects GPS, not GeoJSON)
    start_location = GPS(lat=start_lat, lng=start_lng)
    end_location = GPS(lat=end_lat, lng=end_lng)

    # Create trip attributes
    trip_attributes = TripAttributes(
        driver_type=DriverType.AUTONOMOUS,  # Default for delivery robots
        has_payload=True,  # Assume delivery trips have payload
    )

    # Create fare attributes if available
    fare_attributes = FareAttributes(
        payment_type="mobile_app"  # Default payment type
    )

    # Calculate distance from coordinates if not provided
    distance_meters = trip_data.get('trip_distance_meters', 0)
    if distance_meters == 0 and start_lat and start_lng and end_lat and end_lng:
        # Calculate distance using Haversine formula
        from math import radians, cos, sin, asin, sqrt
        
        def haversine_distance(lat1, lon1, lat2, lon2):
            """Calculate distance between two points using Haversine formula."""
            R = 6371000  # Earth's radius in meters
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            return R * c
        
        distance_meters = int(haversine_distance(start_lat, start_lng, end_lat, end_lng))

    return Trip(
        provider_id=str(settings.PROVIDER_ID_UUID),
        device_id=device_id,
        trip_id=trip_id,
        duration=int(duration_seconds),
        distance=distance_meters,  # Required field in MDS 2.0
        start_location=start_location,
        end_location=end_location,
        start_time=start_time_ms,
        end_time=end_time_ms,
        trip_type=TripType.DELIVERY,
        trip_attributes=trip_attributes,
        fare_attributes=fare_attributes
    )


@router.get(
    "",
    response_model=TripsResponse,
    summary="Get historical trip data",
    description="Returns historical trip data for delivery robots. Requires end_time parameter."
)
async def get_trips(
    request: Request,
    end_time: str = Query(..., description="End time in format YYYY-MM-DDTHH")
):
    """
    Get historical trip data.

    This endpoint returns trip data for the specified hour.
    The end_time parameter must be in format YYYY-MM-DDTHH.
    """
    try:
        # Authenticate request
        provider_id = get_current_provider_id(request)

        # Validate end_time format
        try:
            end_time_dt = datetime.strptime(end_time, "%Y-%m-%dT%H")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_end_time",
                    "error_description": f"Invalid end_time format. Expected YYYY-MM-DDTHH, got: {end_time}"
                }
            )

        # Check if the requested hour is in the future
        now = datetime.utcnow()
        if end_time_dt >= now:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "future_time",
                    "error_description": "Cannot retrieve data for future hours"
                }
            )

        # Check if the requested hour is too far in the past (before operations started)
        # Assuming operations started on 2021-05-01 based on legacy implementation
        operations_start = datetime(2021, 5, 1)
        if end_time_dt < operations_start:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "no_operation",
                    "error_description": "No operations during the requested time period"
                }
            )

        # Check if data is available for this hour
        # data_available = await bigquery_module.bigquery_service.check_data_availability(end_time)

        # Temporarily disable the 202 response for validation purposes
        # hours_ago = (now - end_time_dt).total_seconds() / 3600
        # if hours_ago < 2 and not data_available:  # Data might still be processing
        #     return JSONResponse(
        #         status_code=status.HTTP_202_ACCEPTED,
        #         content={
        #             "error": "data_processing",
        #             "error_description": "Data for this hour is still being processed"
        #         },
        #         headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
        #     )

        # Get trip data for the specified hour
        trip_data = await bigquery_module.bigquery_service.get_robot_trips(end_time_hour=end_time)

        if not trip_data:
            # Return empty trips array for hours with no data (this is valid)
            logger.info(f"No trips found for hour {end_time}")
            return TripsResponse(trips=[])

        # Transform trip data to MDS format
        trips = []
        for trip_record in trip_data:
            try:
                trip = transform_trip_data_to_mds(trip_record)
                trips.append(trip)
            except Exception as e:
                logger.error(f"Failed to transform trip data: {str(e)}")
                continue

        logger.info(f"Returning {len(trips)} trips for hour {end_time}, provider {provider_id}")

        return TripsResponse(trips=trips)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_trips: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "error_description": str(e)}
        )