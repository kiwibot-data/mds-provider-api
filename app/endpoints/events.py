"""
Events endpoints for MDS Provider API.
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request, Query, status
from fastapi.responses import JSONResponse

from app.models.events import EventsResponse, RealtimeEventsResponse, Event
from app.models.common import EventType, VehicleState
from app.services.bigquery import bigquery_service
from app.services.transformers import data_transformer
from app.auth.middleware import get_current_provider_id
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def create_event_from_location_change(
    prev_location: dict,
    current_location: dict
) -> Optional[Event]:
    """
    Create an event based on location data changes.
    This is a simplified approach - in production, integrate with actual robot event systems.
    """
    robot_id = current_location.get('robot_id')
    if not robot_id:
        return None

    device_id = data_transformer.robot_id_to_device_id(robot_id)

    # Determine state change based on location timing
    prev_time = prev_location.get('timestamp') if prev_location else None
    current_time = current_location.get('timestamp')

    if not current_time:
        return None

    # Convert timestamp
    if isinstance(current_time, datetime):
        event_time_ms = int(current_time.timestamp() * 1000)
    else:
        event_time_ms = int(datetime.fromisoformat(str(current_time)).timestamp() * 1000)

    # Determine vehicle state and event type
    vehicle_state = data_transformer.determine_vehicle_state(current_location)
    event_types = data_transformer._get_event_types_for_state(vehicle_state)

    # Create location GeoJSON
    lat = current_location.get('latitude')
    lng = current_location.get('longitude')
    event_location = None
    if lat is not None and lng is not None:
        event_location = data_transformer.transform_location_to_geojson(lat, lng)

    return Event(
        provider_id=settings.PROVIDER_ID,
        device_id=device_id,
        event_types=[EventType(et) for et in event_types],
        vehicle_state=vehicle_state,
        event_time=event_time_ms,
        publication_time=int(datetime.utcnow().timestamp() * 1000),
        event_location=event_location
    )


@router.get(
    "/historical",
    response_model=EventsResponse,
    summary="Get historical events",
    description="Returns historical event data for delivery robots. Requires event_time parameter."
)
async def get_historical_events(
    request: Request,
    event_time: str = Query(..., description="Event time in format YYYY-MM-DDTHH")
):
    """
    Get historical events for a specific hour.

    This endpoint returns event data for the specified hour.
    The event_time parameter must be in format YYYY-MM-DDTHH.
    """
    try:
        # Authenticate request
        provider_id = get_current_provider_id(request)

        # Validate event_time format
        try:
            event_time_dt = datetime.strptime(event_time, "%Y-%m-%dT%H")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "invalid_event_time",
                    "error_details": f"Invalid event_time format. Expected YYYY-MM-DDTHH, got: {event_time}"
                }
            )

        # Check if the requested hour is in the future
        now = datetime.utcnow()
        if event_time_dt >= now:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "future_time",
                    "error_details": "Cannot retrieve data for future hours"
                }
            )

        # Check if the requested hour is too far in the past
        operations_start = datetime(2021, 5, 1)
        if event_time_dt < operations_start:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "no_operation",
                    "error_details": "No operations during the requested time period"
                }
            )

        # Check if data is available for this hour
        data_available = await bigquery_service.check_data_availability(event_time)

        # If the hour is recent but data isn't ready yet, return 202 Accepted
        hours_ago = (now - event_time_dt).total_seconds() / 3600
        if hours_ago < 2 and not data_available:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "error_code": "data_processing",
                    "error_details": "Data for this hour is still being processed"
                },
                headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
            )

        # Create time range for the hour
        start_time = event_time_dt
        end_time = start_time + timedelta(hours=1)

        # Get location data for the hour to derive events
        location_data = await bigquery_service.get_robot_locations(
            since=start_time,
            limit=10000  # Reasonable limit for hourly data
        )

        # Filter location data to the specific hour
        hour_locations = []
        for location in location_data:
            location_time = location.get('timestamp')
            if isinstance(location_time, str):
                location_dt = datetime.fromisoformat(location_time.replace('Z', '+00:00'))
            else:
                location_dt = location_time

            if start_time <= location_dt.replace(tzinfo=None) < end_time:
                hour_locations.append(location)

        if not hour_locations:
            # Return empty events array for hours with no data
            logger.info(f"No events found for hour {event_time}")
            return EventsResponse(events=[])

        # Generate events from location changes
        # Group by robot_id and create state change events
        events = []
        robots_processed = set()

        for location in hour_locations:
            robot_id = location.get('robot_id')
            if robot_id and robot_id not in robots_processed:
                try:
                    event = create_event_from_location_change(None, location)
                    if event:
                        events.append(event)
                    robots_processed.add(robot_id)
                except Exception as e:
                    logger.error(f"Failed to create event for robot {robot_id}: {str(e)}")
                    continue

        logger.info(f"Returning {len(events)} events for hour {event_time}, provider {provider_id}")

        return EventsResponse(events=events)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_historical_events: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "internal_error", "error_details": str(e)}
        )


@router.get(
    "/recent",
    response_model=RealtimeEventsResponse,
    summary="Get recent events",
    description="Near-realtime feed of events less than two weeks old."
)
async def get_recent_events(
    request: Request,
    start_time: int = Query(..., description="Start time timestamp (milliseconds)"),
    end_time: int = Query(..., description="End time timestamp (milliseconds)")
):
    """
    Get recent events within a time range.

    This endpoint returns events that are less than 2 weeks old.
    Both start_time and end_time are required and must be timestamps in milliseconds.
    """
    try:
        # Authenticate request
        provider_id = get_current_provider_id(request)

        # Validate time range
        try:
            start_dt = datetime.fromtimestamp(start_time / 1000)
            end_dt = datetime.fromtimestamp(end_time / 1000)
        except (ValueError, OSError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "invalid_time_range",
                    "error_details": "Invalid timestamp format"
                }
            )

        # Check if time range is valid
        if start_dt >= end_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "invalid_time_range",
                    "error_details": "start_time must be before end_time"
                }
            )

        # Check if time range is within 2 weeks
        now = datetime.utcnow()
        two_weeks_ago = now - timedelta(days=14)

        if start_dt < two_weeks_ago:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "time_range_too_old",
                    "error_details": "start_time cannot be more than 2 weeks ago"
                }
            )

        # Get location data for the time range
        location_data = await bigquery_service.get_robot_locations(
            since=start_dt,
            limit=5000  # Reasonable limit for recent data
        )

        # Filter to exact time range
        filtered_locations = []
        for location in location_data:
            location_time = location.get('timestamp')
            if isinstance(location_time, str):
                location_dt = datetime.fromisoformat(location_time.replace('Z', '+00:00'))
            else:
                location_dt = location_time

            if start_dt <= location_dt.replace(tzinfo=None) < end_dt:
                filtered_locations.append(location)

        # Generate events from location data
        events = []
        robots_processed = set()

        for location in filtered_locations:
            robot_id = location.get('robot_id')
            if robot_id and robot_id not in robots_processed:
                try:
                    event = create_event_from_location_change(None, location)
                    if event:
                        events.append(event)
                    robots_processed.add(robot_id)
                except Exception as e:
                    logger.error(f"Failed to create event for robot {robot_id}: {str(e)}")
                    continue

        # Sort events by event_time
        events.sort(key=lambda x: x.event_time)

        # Calculate response metadata
        current_time = int(datetime.utcnow().timestamp() * 1000)
        ttl = settings.CACHE_TTL_EVENTS * 1000  # Convert to milliseconds

        logger.info(f"Returning {len(events)} recent events for provider {provider_id}")

        return RealtimeEventsResponse(
            events=events,
            last_updated=current_time,
            ttl=ttl
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_recent_events: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "internal_error", "error_details": str(e)}
        )