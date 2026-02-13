"""
Telemetry endpoints for MDS Provider API.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request, Query, status
from fastapi.responses import JSONResponse

from app.models.telemetry import TelemetryResponse, Telemetry, GPS
from app.services.bigquery import bigquery_service
from app.services.transformers import data_transformer
from app.auth.middleware import get_current_provider_id
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def round_gps_coordinate(coord: float, precision: int = 6) -> float:
    """
    Round GPS coordinate to specified precision.
    
    Args:
        coord: Coordinate value (latitude or longitude)
        precision: Number of decimal places (default 6 for differential GPS)
    
    Returns:
        Rounded coordinate
    """
    return round(coord, precision)


@router.get(
    "",
    response_model=TelemetryResponse,
    summary="Get vehicle telemetry data",
    description="Returns GPS telemetry data for delivery robots. Requires telemetry_time parameter."
)
async def get_telemetry(
    request: Request,
    telemetry_time: str = Query(..., description="Telemetry time in format YYYY-MM-DDTHH")
):
    """
    Get telemetry data for a specific hour.

    This endpoint returns GPS telemetry points for the specified hour.
    The telemetry_time parameter must be in format YYYY-MM-DDTHH.
    """
    request_id = id(request)
    logger.info(f"[{request_id}] Starting telemetry request for {telemetry_time}")
    
    try:
        # Authenticate request
        logger.debug(f"[{request_id}] Authenticating request")
        provider_id = get_current_provider_id(request)
        logger.debug(f"[{request_id}] Authenticated as provider: {provider_id}")

        # Validate telemetry_time format
        try:
            telemetry_time_dt = datetime.strptime(telemetry_time, "%Y-%m-%dT%H")
            logger.debug(f"[{request_id}] Parsed telemetry_time: {telemetry_time_dt}")
        except ValueError as ve:
            logger.error(f"[{request_id}] Invalid time format: {ve}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_telemetry_time",
                    "error_description": f"Invalid telemetry_time format. Expected YYYY-MM-DDTHH, got: {telemetry_time}"
                }
            )

        # Check if the requested hour is in the future
        # Temporarily disabled for testing with future data
        # now = datetime.utcnow()
        # if telemetry_time_dt >= now:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail={
        #             "error_code": "future_time",
        #             "error_details": "Cannot retrieve data for future hours"
        #         }
        #     )

        # Check if the requested hour is too far in the past
        operations_start = datetime(2021, 5, 1)
        if telemetry_time_dt < operations_start:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "no_operation",
                    "error_description": "No operations during the requested time period"
                }
            )

        # Get telemetry data for the specified hour
        logger.info(f"[{request_id}] Querying BigQuery for telemetry data")
        try:
            telemetry_data = await bigquery_service.get_robot_telemetry(telemetry_time)
            logger.info(f"[{request_id}] Retrieved {len(telemetry_data) if telemetry_data else 0} telemetry records")
        except Exception as bq_error:
            logger.error(f"[{request_id}] BigQuery error: {str(bq_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "database_error",
                    "error_description": "Failed to retrieve telemetry data"
                }
            )

        if not telemetry_data:
            logger.info(f"[{request_id}] No telemetry found for hour {telemetry_time}")
            return TelemetryResponse(telemetry=[])

        # Transform telemetry data to MDS format
        telemetry_points = []
        from uuid import uuid5, NAMESPACE_DNS

        for telemetry_record in telemetry_data:
            try:
                robot_id = telemetry_record.get('robot_id')
                if not robot_id:
                    continue

                device_id = data_transformer.robot_id_to_device_id(robot_id)

                # Parse timestamps - use trip_start for start point, trip_end for end point
                start_time = telemetry_record.get('trip_start')
                end_time = telemetry_record.get('trip_end')

                if isinstance(start_time, datetime):
                    start_time_ms = int(start_time.timestamp() * 1000)
                else:
                    start_time_ms = int(start_time * 1000) if start_time else 0

                if isinstance(end_time, datetime):
                    end_time_ms = int(end_time.timestamp() * 1000)
                else:
                    end_time_ms = int(end_time * 1000) if end_time else 0

                # Extract or generate trip_id and journey_id
                job_id = telemetry_record.get('job_id') or telemetry_record.get('id') or robot_id
                trip_id = data_transformer._generate_trip_id({'job_id': job_id})
                journey_id = uuid5(NAMESPACE_DNS, f"{settings.PROVIDER_ID}.journey.{job_id}")

                # Create start point telemetry
                start_lat = telemetry_record.get('start_latitude')
                start_lng = telemetry_record.get('start_longitude')
                if start_lat is not None and start_lng is not None and start_time_ms > 0:
                    start_gps = GPS(
                        lat=round_gps_coordinate(start_lat),
                        lng=round_gps_coordinate(start_lng),
                        horizontal_accuracy=5.0  # Default GPS accuracy in meters
                    )
                    # Generate unique telemetry_id for this point
                    start_telemetry_id = uuid5(NAMESPACE_DNS, f"{settings.PROVIDER_ID}.telemetry.{device_id}.{start_time_ms}")

                    start_telemetry = Telemetry(
                        provider_id=settings.PROVIDER_ID_UUID,
                        device_id=device_id,
                        telemetry_id=start_telemetry_id,
                        timestamp=start_time_ms,
                        trip_ids=[trip_id],
                        journey_id=journey_id,
                        location=start_gps
                    )
                    telemetry_points.append(start_telemetry)

                # Create end point telemetry
                end_lat = telemetry_record.get('end_latitude')
                end_lng = telemetry_record.get('end_longitude')
                if end_lat is not None and end_lng is not None and end_time_ms > 0:
                    end_gps = GPS(
                        lat=round_gps_coordinate(end_lat),
                        lng=round_gps_coordinate(end_lng),
                        horizontal_accuracy=5.0  # Default GPS accuracy in meters
                    )
                    # Generate unique telemetry_id for this point
                    end_telemetry_id = uuid5(NAMESPACE_DNS, f"{settings.PROVIDER_ID}.telemetry.{device_id}.{end_time_ms}")

                    end_telemetry = Telemetry(
                        provider_id=settings.PROVIDER_ID_UUID,
                        device_id=device_id,
                        telemetry_id=end_telemetry_id,
                        timestamp=end_time_ms,
                        trip_ids=[trip_id],
                        journey_id=journey_id,
                        location=end_gps
                    )
                    telemetry_points.append(end_telemetry)

            except Exception as e:
                logger.error(f"Failed to transform telemetry data: {str(e)}")
                continue

        # Sort telemetry by timestamp
        telemetry_points.sort(key=lambda x: x.timestamp)

        logger.info(f"[{request_id}] Successfully returning {len(telemetry_points)} telemetry points for hour {telemetry_time}")

        return TelemetryResponse(telemetry=telemetry_points)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error in get_telemetry: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "error_description": "Internal server error"}
        )
