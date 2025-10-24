"""
Events endpoints for MDS Provider API.
"""

import logging
from typing import Optional
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

    # Generate event_id UUID from event data
    from uuid import uuid5, NAMESPACE_DNS
    event_id_str = f"{settings.PROVIDER_ID}.event.{robot_id}.{event_time_ms}"
    event_id = uuid5(NAMESPACE_DNS, event_id_str)

    return Event(
        event_id=event_id,
        provider_id=settings.PROVIDER_ID_UUID,
        device_id=device_id,
        event_types=[EventType(et) for et in event_types],
        vehicle_state=vehicle_state,
        timestamp=event_time_ms,
        publication_time=int(datetime.utcnow().timestamp() * 1000),
        location=event_location
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
        # Temporarily disabled for testing with future data
        # now = datetime.utcnow()
        # if event_time_dt >= now:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail={
        #             "error_code": "future_time",
        #             "error_details": "Cannot retrieve data for future hours"
        #         }
        #     )

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
        now = datetime.utcnow()
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

        # Create time range for the hour (ensure timezone-aware)
        from datetime import timezone
        start_time = event_time_dt.replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(hours=1)

        # Get events data directly from the pre-computed events table
        events_data = await bigquery_service.get_robot_events(
            since=start_time,
            until=end_time,
            limit=10000  # Reasonable limit for hourly data
        )

        # Debug: Log the number of events returned
        logger.info(f"BigQuery returned {len(events_data) if events_data else 0} events for hour {event_time}")

        if not events_data:
            # Return empty events array for hours with no data
            logger.info(f"No events found for hour {event_time}")
            return EventsResponse(events=[])

        # Transform events data to MDS format
        events = []
        logger.info(f"Processing {len(events_data)} events from BigQuery")
        for i, event_data in enumerate(events_data):
            try:
                # Convert event data to MDS Event format
                robot_id = event_data.get('robot_id')
                if not robot_id:
                    continue

                device_id = data_transformer.robot_id_to_device_id(robot_id)
                
                # Parse event time
                event_time = event_data.get('event_time')
                if isinstance(event_time, datetime):
                    event_time_ms = int(event_time.timestamp() * 1000)
                else:
                    event_time_ms = int(datetime.fromisoformat(str(event_time)).timestamp() * 1000)

                # Create location GeoJSON
                lat = event_data.get('latitude')
                lng = event_data.get('longitude')
                event_location = None
                if lat is not None and lng is not None:
                    event_location = data_transformer.transform_location_to_geojson(lat, lng)

                # Determine event type and vehicle state from event_type
                event_type_str = event_data.get('event_type', 'other')
                if event_type_str == 'trip_start':
                    event_types = [EventType.TRIP_START]
                    vehicle_state = VehicleState.ON_TRIP
                elif event_type_str == 'trip_end':
                    event_types = [EventType.TRIP_END]
                    vehicle_state = VehicleState.AVAILABLE
                else:
                    event_types = [EventType.LOCATED]
                    vehicle_state = VehicleState.AVAILABLE

                # Generate event_id UUID from event data
                event_id = data_transformer._generate_event_id(event_data)

                event = Event(
                    event_id=event_id,
                    provider_id=settings.PROVIDER_ID_UUID,
                    device_id=device_id,
                    event_types=event_types,
                    vehicle_state=vehicle_state,
                    timestamp=event_time_ms,
                    publication_time=int(datetime.utcnow().timestamp() * 1000),
                    location=event_location
                )
                events.append(event)
            except Exception as e:
                logger.error(f"Failed to transform event data: {str(e)}")
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

        # Get events data directly from the pre-computed events table
        # Ensure timezone-aware datetimes
        from datetime import timezone
        start_dt_utc = start_dt.replace(tzinfo=timezone.utc)
        end_dt_utc = end_dt.replace(tzinfo=timezone.utc)
        
        events_data = await bigquery_service.get_robot_events(
            since=start_dt_utc,
            until=end_dt_utc,
            limit=5000  # Reasonable limit for recent data
        )

        # Transform events data to MDS format
        events = []
        for event_data in events_data:
            try:
                # Convert event data to MDS Event format
                robot_id = event_data.get('robot_id')
                if not robot_id:
                    continue

                device_id = data_transformer.robot_id_to_device_id(robot_id)
                
                # Parse event time
                event_time = event_data.get('event_time')
                if isinstance(event_time, datetime):
                    event_time_ms = int(event_time.timestamp() * 1000)
                else:
                    event_time_ms = int(datetime.fromisoformat(str(event_time)).timestamp() * 1000)

                # Create location GeoJSON
                lat = event_data.get('latitude')
                lng = event_data.get('longitude')
                event_location = None
                if lat is not None and lng is not None:
                    event_location = data_transformer.transform_location_to_geojson(lat, lng)

                # Determine event type and vehicle state from event_type
                event_type_str = event_data.get('event_type', 'other')
                if event_type_str == 'trip_start':
                    event_types = [EventType.TRIP_START]
                    vehicle_state = VehicleState.ON_TRIP
                elif event_type_str == 'trip_end':
                    event_types = [EventType.TRIP_END]
                    vehicle_state = VehicleState.AVAILABLE
                else:
                    event_types = [EventType.LOCATED]
                    vehicle_state = VehicleState.AVAILABLE

                # Generate event_id UUID from event data
                event_id = data_transformer._generate_event_id(event_data)

                event = Event(
                    event_id=event_id,
                    provider_id=settings.PROVIDER_ID_UUID,
                    device_id=device_id,
                    event_types=event_types,
                    vehicle_state=vehicle_state,
                    timestamp=event_time_ms,
                    publication_time=int(datetime.utcnow().timestamp() * 1000),
                    location=event_location
                )
                events.append(event)
            except Exception as e:
                logger.error(f"Failed to transform event data: {str(e)}")
                continue

        # Sort events by timestamp
        events.sort(key=lambda x: x.timestamp)

        logger.info(f"Returning {len(events)} recent events for provider {provider_id}")

        return RealtimeEventsResponse(
            events=events
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_recent_events: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "internal_error", "error_details": str(e)}
        )